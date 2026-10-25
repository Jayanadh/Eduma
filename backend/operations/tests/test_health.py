"""Health, alerts, usage and the restore check (BUILD-11 S11-04..08)."""

import datetime as dt
import json

import pytest
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from operations import services
from operations.models import Alert, BackupRecord, JobRun, RestoreDrill

P = "/api/v1/platform"


def tile(key):
    return next(t for t in services.health() if t["key"] == key)


def test_missing_telemetry_is_unknown_not_healthy(db):
    assert (tile("worker")["status"], tile("worker")["value"]) == ("unknown", "never seen")
    assert tile("backup")["status"] == "unknown" and tile("restore")["status"] == "unknown"
    assert tile("payments")["status"] == "not_configured"
    services.evaluate_alerts()
    assert not Alert.objects.exists()


def test_a_stopped_worker_raises_an_alert_that_clears_on_recovery(db):
    services.run_jobs()
    assert tile("worker")["status"] == "ok"
    assert {"heartbeat", "exports", "expire_exports", "overdue_cases", "alerts"} <= set(
        JobRun.objects.values_list("task", flat=True)
    )
    JobRun.objects.filter(task="heartbeat").update(started_at=timezone.now() - dt.timedelta(minutes=12))
    [alert] = [a for a in services.evaluate_alerts() if a.key == "worker"]
    assert (alert.severity, alert.state) == ("critical", "open")
    assert alert.summary == "Worker: last heartbeat 12 min ago (expected within 5 min)"
    assert alert.runbook == "docs/operations.md#worker"
    services.run_jobs()  # the worker is back
    alert.refresh_from_db()
    assert alert.state == "resolved" and alert.resolved_at


def test_an_outside_monitor_sees_a_dead_worker_and_raises_the_alert(world, client_for):
    probe = client_for(None)
    assert probe.get("/api/v1/health/ready").json() == {"status": "degraded", "failing": ["worker"]}  # never seen
    services.run_jobs()
    assert probe.get("/api/v1/health/ready").status_code == 200
    JobRun.objects.update(started_at=timezone.now() - dt.timedelta(minutes=12))
    Alert.objects.all().delete()
    stale = probe.get("/api/v1/health/ready")
    assert stale.status_code == 503 and stale.json()["failing"] == ["worker"]
    assert Alert.objects.get(key="worker").state == "open"  # raised without the worker


def test_platform_pages_are_for_platform_admins(world, client_for):
    services.run_jobs()
    JobRun.objects.filter(task="heartbeat").update(started_at=timezone.now() - dt.timedelta(minutes=12))
    services.evaluate_alerts()
    console = client_for(None, world.platform_admin)
    health = console.get(f"{P}/health").json()
    assert {t["key"] for t in health["tiles"]} >= {"database", "worker", "exports", "storage", "backup", "restore"}
    assert all("observed_at" in t and t["threshold"] for t in health["tiles"])
    [alert] = health["alerts"]
    done = console.post(f"{P}/alerts/{alert['id']}/acknowledge").json()
    assert (done["state"], done["owner"]) == ("acknowledged", world.platform_admin.full_name)
    assert client_for(world.a.slug, world.a_admin).get(f"{P}/health").status_code in (403, 404)
    usage = {u["institution"]["slug"]: u for u in console.get(f"{P}/usage").json()}
    assert usage["aster"]["members"] == {"staff": 1} and usage["aster"]["active_students"] == 0


@pytest.mark.django_db(transaction=True)
def test_restore_check_compares_counts_and_balances(world, capsys):
    BackupRecord.objects.create(
        taken_at=timezone.now(), database_file="db.dump", database_sha256="a" * 64, media_file="m.tar",
        media_sha256="b" * 64, size_bytes=10,
    )  # fmt: skip
    call_command("restore_check", restored=connection.settings_dict["NAME"], seconds=12.34)
    printed = json.loads(capsys.readouterr().out)
    assert printed["passed"] is True and printed["different_tables"] == {} and printed["trial_balances_match"]
    drill = RestoreDrill.objects.get()
    assert drill.passed and str(drill.seconds) == "12.3"
    assert tile("restore")["status"] == "ok"


@pytest.mark.django_db(transaction=True)  # the workload's threads read through their own connections
def test_the_workload_runs_every_persona_without_errors(settings, capsys):
    settings.DEBUG = True
    call_command("seed_demo", stdout=open("/dev/null", "w"))
    call_command("measure_workload", clients=1, rounds=1)
    out = capsys.readouterr().out
    assert "Worst p95" in out and out.count("errors 0") == out.count(" ms  p95 ")
