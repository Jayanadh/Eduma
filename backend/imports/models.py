"""Staged imports (spec pack 11 §6, slice 4c §3): a file is parsed into rows and checked before anything reaches the
real records; what a commit creates remembers its source (ImportedRecord), so a re-run never creates it twice."""

import uuid

from django.conf import settings
from django.db import models

from admissions.models import private_storage
from common.models import VersionedModel


def import_path(job, filename: str) -> str:
    return f"imports/{job.institution_id}/{uuid.uuid4()}.csv"


class ImportJob(VersionedModel):
    class Status(models.TextChoices):
        VALIDATED = "validated", "Checked, not imported"
        COMMITTED = "committed", "Imported"
        DISCARDED = "discarded", "Discarded"
        UNDONE = "undone", "Undone"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="imports")
    contract = models.CharField(max_length=20, default="students-v1")
    source_system = models.CharField(max_length=60)
    file = models.FileField(storage=private_storage, upload_to=import_path, max_length=200, blank=True)
    original_name = models.CharField(max_length=200)
    checksum = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VALIDATED)
    totals = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    committed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    committed_at = models.DateTimeField(null=True, blank=True)
    undone_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    undone_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ImportRow(models.Model):
    class State(models.TextChoices):
        VALID = "valid", "Ready"
        ERROR = "error", "Has errors"
        DUPLICATE = "duplicate", "Possible duplicate"
        UNCHANGED = "unchanged", "Already imported"
        CHANGED = "changed", "Changed since the last import"

    class Decision(models.TextChoices):
        NONE = "", "Not decided"
        CREATE = "create", "Create a new student"
        SKIP = "skip", "Skip"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField()
    source_record_id = models.CharField(max_length=100, blank=True)
    raw = models.JSONField(default=dict)
    errors = models.JSONField(default=list)
    state = models.CharField(max_length=10, choices=State.choices)
    duplicate_of = models.JSONField(default=list)
    decision = models.CharField(max_length=6, choices=Decision.choices, blank=True, default="")
    checksum = models.CharField(max_length=64, blank=True)
    student = models.ForeignKey("students.Student", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["row_number"]
        constraints = [models.UniqueConstraint(fields=["job", "row_number"], name="one_row_number_per_job")]


class ImportedRecord(models.Model):
    """Where an imported record came from. Source ids are provenance, never trusted as Eduma ids."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    source_system = models.CharField(max_length=60)
    entity_type = models.CharField(max_length=20)
    source_record_id = models.CharField(max_length=100)
    checksum = models.CharField(max_length=64)
    job = models.ForeignKey(ImportJob, on_delete=models.PROTECT, related_name="records")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="provenance")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "source_system", "entity_type", "source_record_id"],
                name="one_import_per_source_record",
            )
        ]
