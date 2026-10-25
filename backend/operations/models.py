"""Exports, job runs, alerts, backups and restore drills (BUILD-11 S11-03..08)."""

import uuid

from django.conf import settings
from django.db import models

from admissions.models import private_storage


def _id():
    return models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


def export_path(job, filename: str) -> str:
    return f"exports/{job.institution_id}/{job.id}/{filename}"


class ExportJob(models.Model):
    class State(models.TextChoices):
        QUEUED = "queued", "Waiting"
        RUNNING = "running", "Running"
        DONE = "done", "Ready"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    report = models.CharField(max_length=40)
    filters = models.JSONField(default=dict)
    state = models.CharField(max_length=10, choices=State.choices, default=State.QUEUED)
    file = models.FileField(storage=private_storage, upload_to=export_path, blank=True)
    rows = models.PositiveIntegerField(null=True, blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class JobRun(models.Model):
    id = _id()
    task = models.CharField(max_length=40)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10)  # ok / failed
    detail = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["task", "-started_at"])]


class Alert(models.Model):
    class State(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    id = _id()
    key = models.CharField(max_length=40)  # the health check it is about
    severity = models.CharField(max_length=10)  # warning / critical
    summary = models.CharField(max_length=200)
    runbook = models.CharField(max_length=120)
    state = models.CharField(max_length=12, choices=State.choices, default=State.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]


class BackupRecord(models.Model):
    id = _id()
    taken_at = models.DateTimeField()
    database_file = models.CharField(max_length=200)
    database_sha256 = models.CharField(max_length=64)
    media_file = models.CharField(max_length=200)
    media_sha256 = models.CharField(max_length=64)
    size_bytes = models.BigIntegerField()

    class Meta:
        ordering = ["-taken_at"]


class RestoreDrill(models.Model):
    id = _id()
    backup = models.ForeignKey(BackupRecord, on_delete=models.PROTECT, related_name="drills")
    ran_at = models.DateTimeField()
    seconds = models.DecimalField(max_digits=8, decimal_places=1)
    passed = models.BooleanField()
    detail = models.JSONField()

    class Meta:
        ordering = ["-ran_at"]
