"""University affiliation (slice 5e S5E-01..04): an explicit grant lets a college send result batches across the
tenant boundary; the university keeps snapshots and never changes the college's records."""

import uuid

from django.conf import settings
from django.db import models

from common.models import VersionedModel


class AffiliationGrant(VersionedModel):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Waiting for the college's approval"
        ACTIVE = "active", "Approved"
        REVOKED = "revoked", "Revoked"

    # The data categories and action every grant covers in this slice (S5E-01).
    CATEGORIES = ("identity", "program_and_regulation", "course_attempts")
    ACTIONS = ("submit_result_batches",)

    college = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="grants_given")
    university = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="grants_received")
    purpose = models.CharField(max_length=300)
    starts_on = models.DateField()
    ends_on = models.DateField()
    evidence = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PROPOSED)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]


class SubmissionBatch(models.Model):
    """One revision of a result batch. Revisions of one batch share its reference."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grant = models.ForeignKey(AffiliationGrant, on_delete=models.PROTECT, related_name="batches")
    reference = models.UUIDField(default=uuid.uuid4)
    revision = models.PositiveSmallIntegerField(default=1)
    program_code = models.CharField(max_length=20)
    term_label = models.CharField(max_length=80)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["reference", "revision"], name="unique_batch_revision")]


class SubmissionRow(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for review"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Returned for correction"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(SubmissionBatch, on_delete=models.CASCADE, related_name="rows")
    # The college's student, for re-snapshotting a correction; the university only ever reads the snapshot fields.
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=20)
    full_name = models.CharField(max_length=150)
    program = models.CharField(max_length=20)
    regulation = models.CharField(max_length=40)
    attempts = models.JSONField(default=list)
    problems = models.JSONField(default=list)
    is_correction = models.BooleanField(default=False)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    reason = models.CharField(max_length=300, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
