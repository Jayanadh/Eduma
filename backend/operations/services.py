"""Exports, jobs, health, alerts and usage (BUILD-11 S11-03..07)."""

import csv
import datetime as dt
import io
import tempfile
import time
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from accounts.models import Membership
from accounts.permissions import has_perm
from common.exceptions import Problem
from imports.services import _safe
from operations import reports
from operations.models import Alert, BackupRecord, ExportJob, JobRun, RestoreDrill

EXPORT = "report.export"
EXPORT_DAYS = 7
HEARTBEAT_STALE = dt.timedelta(minutes=5)
SCHEDULE = {"expire_exports": dt.timedelta(hours=1), "overdue_cases": dt.timedelta(days=1)}


# Exports (S11-03)


def _may_export(actor, institution, report) -> bool:
    return has_perm(actor, institution, EXPORT) and reports.may_run(actor, institution, report)


def request_export(actor, institution, report) -> ExportJob:
    if not _may_export(actor, institution, report):
        raise PermissionDenied("You can't export this report.")
    return ExportJob.objects.create(institution=institution, requester=actor, report=report.key)


def build_export(job: ExportJob) -> ExportJob:
    """Run one export as its requester, so it holds only what they may read at the time it runs."""
    report = reports.REPORTS[job.report]
    ExportJob.objects.filter(pk=job.pk).update(state=ExportJob.State.RUNNING)
    try:
        if not _may_export(job.requester, job.institution, report):
            raise PermissionDenied("The requester can no longer export this report.")
        result = reports.run(job.requester, job.institution, report)
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(result["columns"])
        for row in result["rows"]:
            writer.writerow([_safe(str(cell)) for cell in row])
        job.file.save(f"{report.key}.csv", ContentFile(out.getvalue().encode()), save=False)
        job.state, job.rows = ExportJob.State.DONE, len(result["rows"])
        job.expires_at = timezone.now() + dt.timedelta(days=EXPORT_DAYS)
    except Exception as error:  # a failed export says why and never leaves a half file
        job.state, job.error = ExportJob.State.FAILED, str(error)[:300]
    job.finished_at = timezone.now()
    job.save()
    return job


def download(actor, institution, job: ExportJob):
    if job.requester_id != actor.id:
        raise PermissionDenied("Only who asked for an export downloads it.")
    if not _may_export(actor, institution, reports.REPORTS[job.report]):
        raise PermissionDenied("You can no longer export this report.")
    if job.state == ExportJob.State.EXPIRED or (job.expires_at and job.expires_at < timezone.now()):
        raise Problem(410, "export_expired", "This export has expired; ask for it again.")
    if job.state != ExportJob.State.DONE:
        raise Problem(409, "export_not_ready", "This export isn't ready yet.")
    return job.file.open("rb")


def export_item(job: ExportJob) -> dict:
    return {
        "id": str(job.id),
        "report": job.report,
        "title": reports.REPORTS[job.report].title,
        "state": job.state,
        "rows": job.rows,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
    }


# Jobs (S11-04)


def _record(task: str, work) -> JobRun:
    run = JobRun.objects.create(task=task, started_at=timezone.now(), status="running")
    try:
        detail = work() or ""
        run.status = "ok"
    except Exception as error:
        detail, run.status = f"{type(error).__name__}: {error}", "failed"
    run.detail, run.finished_at = str(detail)[:300], timezone.now()
    run.save()
    return run


def _expire_exports() -> str:
    gone = 0
    for job in ExportJob.objects.filter(state=ExportJob.State.DONE, expires_at__lt=timezone.now()):
        job.file.delete(save=False)
        job.state = ExportJob.State.EXPIRED
        job.save(update_fields=["file", "state"])
        gone += 1
    return f"{gone} expired"


def _overdue_cases() -> str:
    from cases.models import ServiceCase
    from communication.services import notify

    late = ServiceCase.objects.filter(
        state=ServiceCase.State.ASSIGNED, due_at__lt=timezone.now(), assignee__isnull=False
    ).select_related("assignee__user", "institution")
    for case in late:
        notify(
            case.assignee.user, case.institution, f"{case.number} is past its response date.", f"/app/cases/{case.id}"
        )
    return f"{late.count()} reminded"


def _exports() -> str:
    done = 0
    for job in ExportJob.objects.filter(state=ExportJob.State.QUEUED).select_related("requester", "institution")[:20]:
        build_export(job)
        done += 1
    return f"{done} built"


def run_jobs(now=None) -> list[JobRun]:
    """One pass of the worker: heartbeat, queued exports, due scheduled tasks, then alerts."""
    now = now or timezone.now()
    runs = [_record("heartbeat", lambda: "alive"), _record("exports", _exports)]
    tasks = {"expire_exports": _expire_exports, "overdue_cases": _overdue_cases}
    for task, every in SCHEDULE.items():
        last = JobRun.objects.filter(task=task, status="ok").first()
        if last is None or last.started_at <= now - every:
            runs.append(_record(task, tasks[task]))
    runs.append(_record("alerts", lambda: f"{len(evaluate_alerts())} open"))
    return runs


# Health (S11-05)


def _tile(key, label, status, value, threshold, source, runbook, observed=None) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "value": value,
        "threshold": threshold,
        "source": source,
        "runbook": runbook,
        "observed_at": (observed or timezone.now()).isoformat(),
    }


def _age(moment) -> str:
    seconds = int((timezone.now() - moment).total_seconds())
    return f"{seconds // 3600} h {seconds % 3600 // 60} min ago" if seconds >= 3600 else f"{seconds // 60} min ago"


def health() -> list[dict]:
    from communication.models import MediaConfig
    from fees.models import ProviderConfig

    tiles, now = [], timezone.now()
    try:
        start = time.monotonic()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        ms = (time.monotonic() - start) * 1000
        tiles.append(
            _tile(
                "database",
                "Database",
                "ok" if ms < 200 else "warning",
                f"{ms:.0f} ms round trip",
                "under 200 ms",
                "SELECT 1",
                "docs/operations.md#database",
            )
        )
    except Exception:
        tiles.append(
            _tile(
                "database",
                "Database",
                "failing",
                "not reachable",
                "reachable",
                "SELECT 1",
                "docs/operations.md#database",
            )
        )
    beat = JobRun.objects.filter(task="heartbeat", status="ok").first()
    if beat is None:
        tiles.append(
            _tile(
                "worker",
                "Worker",
                "unknown",
                "never seen",
                "a heartbeat every minute",
                "run_jobs",
                "docs/operations.md#worker",
            )
        )
    else:
        stale = beat.started_at < now - HEARTBEAT_STALE
        tiles.append(
            _tile(
                "worker",
                "Worker",
                "failing" if stale else "ok",
                f"last heartbeat {_age(beat.started_at)}",
                "within 5 min",
                "run_jobs",
                "docs/operations.md#worker",
                beat.started_at,
            )
        )
    oldest = ExportJob.objects.filter(state=ExportJob.State.QUEUED).order_by("created_at").first()
    waiting = (now - oldest.created_at) if oldest else dt.timedelta(0)
    queue = (
        "ok" if waiting < dt.timedelta(minutes=10) else "warning" if waiting < dt.timedelta(minutes=30) else "failing"
    )
    tiles.append(
        _tile(
            "exports",
            "Export queue",
            queue,
            f"oldest waiting {_age(oldest.created_at)}" if oldest else "empty",
            "under 10 min",
            "ExportJob",
            "docs/operations.md#exports",
        )
    )
    root = Path(settings.PRIVATE_MEDIA_ROOT)
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=root):
            pass
        tiles.append(
            _tile(
                "storage",
                "Private storage",
                "ok",
                "writable",  # sizes are per institution on Usage; this check stays cheap enough to probe often
                "writable",
                "private media",
                "docs/operations.md#storage",
            )
        )
    except OSError:
        tiles.append(
            _tile(
                "storage",
                "Private storage",
                "failing",
                "not writable",
                "writable",
                "private media",
                "docs/operations.md#storage",
            )
        )
    backup = BackupRecord.objects.first()
    if backup is None:
        tiles.append(
            _tile(
                "backup",
                "Last backup",
                "unknown",
                "none recorded",
                "within 26 h",
                "ops/backup.sh",
                "docs/operations.md#backup",
            )
        )
    else:
        late = backup.taken_at < now - dt.timedelta(hours=26)
        tiles.append(
            _tile(
                "backup",
                "Last backup",
                "failing" if late else "ok",
                _age(backup.taken_at),
                "within 26 h",
                "ops/backup.sh",
                "docs/operations.md#backup",
                backup.taken_at,
            )
        )
    drill = RestoreDrill.objects.first()
    if drill is None:
        tiles.append(
            _tile(
                "restore",
                "Restore drill",
                "unknown",
                "never run",
                "a passing drill within 35 days",
                "ops/restore-drill.sh",
                "docs/operations.md#restore",
            )
        )
    else:
        good = drill.passed and drill.ran_at >= now - dt.timedelta(days=35)
        tiles.append(
            _tile(
                "restore",
                "Restore drill",
                "ok" if good else "warning",
                f"{'passed' if drill.passed else 'FAILED'} {_age(drill.ran_at)} in {drill.seconds} s",
                "a passing drill within 35 days",
                "ops/restore-drill.sh",
                "docs/operations.md#restore",
                drill.ran_at,
            )
        )
    media = MediaConfig.objects.exclude(provider="sandbox").count()
    tiles.append(
        _tile(
            "media",
            "Calls and classes provider",
            "ok" if media else "not_configured",
            f"{media} live" if media else "test-mode sandbox only",
            "a live provider (D-12)",
            "MediaConfig",
            "docs/operations.md#providers",
        )
    )
    payments = ProviderConfig.objects.count()
    tiles.append(
        _tile(
            "payments",
            "Payment provider",
            "not_configured",
            f"{payments} institution(s) on the sandbox" if payments else "none",
            "a live provider",
            "ProviderConfig",
            "docs/operations.md#providers",
        )
    )
    return tiles


# Alerts (S11-06)


def evaluate_alerts(tiles=None) -> list[Alert]:
    tiles = tiles if tiles is not None else health()
    now = timezone.now()
    with transaction.atomic():
        for tile in tiles:
            live = Alert.objects.filter(key=tile["key"]).exclude(state=Alert.State.RESOLVED).first()
            if tile["status"] in ("failing", "warning"):
                summary = f"{tile['label']}: {tile['value']} (expected {tile['threshold']})"
                if live is None:
                    Alert.objects.create(
                        key=tile["key"],
                        severity="critical" if tile["status"] == "failing" else "warning",
                        summary=summary,
                        runbook=tile["runbook"],
                        last_seen_at=now,
                    )
                else:
                    live.summary, live.last_seen_at = summary, now
                    live.save(update_fields=["summary", "last_seen_at"])
            elif tile["status"] == "ok" and live is not None:
                live.state, live.resolved_at = Alert.State.RESOLVED, now
                live.save(update_fields=["state", "resolved_at"])
    return list(Alert.objects.exclude(state=Alert.State.RESOLVED))


def acknowledge(actor, alert: Alert) -> Alert:
    if alert.state == Alert.State.RESOLVED:
        raise Problem(409, "invalid_transition", "This alert is already resolved.")
    alert.state, alert.owner, alert.acknowledged_at = Alert.State.ACKNOWLEDGED, actor, timezone.now()
    alert.save(update_fields=["state", "owner", "acknowledged_at"])
    return alert


def alert_item(a: Alert) -> dict:
    return {
        "id": str(a.id),
        "key": a.key,
        "severity": a.severity,
        "summary": a.summary,
        "runbook": a.runbook,
        "state": a.state,
        "opened_at": a.opened_at.isoformat(),
        "last_seen_at": a.last_seen_at.isoformat(),
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "owner": a.owner.full_name if a.owner_id else None,
    }


# Usage (S11-07)


def usage(institution) -> dict:
    from cases.models import ServiceCase
    from communication.models import Message

    month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    kinds = dict(
        Membership.objects.filter(institution=institution, status=Membership.Status.ACTIVE)
        .values("kind")
        .annotate(n=Count("id"))
        .values_list("kind", "n")
    )
    size = 0
    for top in Path(settings.PRIVATE_MEDIA_ROOT).glob(f"*/{institution.id}"):
        size += sum(f.stat().st_size for f in top.rglob("*") if f.is_file())
    return {
        "institution": {"id": str(institution.id), "name": institution.display_name, "slug": institution.slug},
        "members": kinds,
        "active_students": institution.students.filter(status="active").count(),
        "exports_this_month": ExportJob.objects.filter(institution=institution, created_at__gte=month).count(),
        "messages_this_month": Message.objects.filter(
            conversation__institution=institution, created_at__gte=month
        ).count(),
        "open_cases": ServiceCase.objects.filter(institution=institution).exclude(state="resolved").count(),
        "storage_bytes": size,
    }
