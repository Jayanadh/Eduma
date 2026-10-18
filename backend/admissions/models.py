"""Admissions: a cycle with its places, questions and required documents (slice 4a spec §3). A cycle is edited only
while it is a draft; publishing freezes it, so the published cycle is the form every application answered."""

import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from common.models import VersionedModel


def private_storage() -> FileSystemStorage:
    """Applicants' documents live outside the public media path (slice 4a S4-09)."""
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def document_path(document, filename: str) -> str:
    return f"applications/{document.application.institution_id}/{document.application_id}/{filename}"


class AdmissionCycle(VersionedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Open for applications"
        CLOSED = "closed", "Closed"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="cycles")
    name = models.CharField(max_length=120)
    # The academic year applicants join: entry_year 2027 → "2027–28" (by the institution's year start).
    entry_year = models.PositiveIntegerField()
    academic_year = models.CharField(max_length=20)
    opens_on = models.DateField()
    closes_on = models.DateField()
    instructions = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-opens_on", "name"]

    def __str__(self) -> str:
        return self.name


class Place(models.Model):
    """What one applies for: a class, grade or programme, with its seats."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle = models.ForeignKey(AdmissionCycle, on_delete=models.CASCADE, related_name="places")
    code = models.CharField(max_length=20)
    label = models.CharField(max_length=80)
    campus = models.ForeignKey("organization.Campus", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    seats = models.PositiveIntegerField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        constraints = [models.UniqueConstraint(fields=["cycle", "code"], name="unique_place_code")]

    def __str__(self) -> str:
        return self.label


class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Kind(models.TextChoices):
        TEXT = "text", "Short answer"
        LONG_TEXT = "long_text", "Long answer"
        DATE = "date", "Date"
        CHOICE = "choice", "Choice"
        YES_NO = "yes_no", "Yes or no"

    cycle = models.ForeignKey(AdmissionCycle, on_delete=models.CASCADE, related_name="questions")
    code = models.CharField(max_length=20)
    label = models.CharField(max_length=200)
    help = models.CharField(max_length=300, blank=True)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    options = models.JSONField(default=list, blank=True)
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        constraints = [models.UniqueConstraint(fields=["cycle", "code"], name="unique_question_code")]


class DocumentRequirement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle = models.ForeignKey(AdmissionCycle, on_delete=models.CASCADE, related_name="documents")
    code = models.CharField(max_length=20)
    label = models.CharField(max_length=120)
    help = models.CharField(max_length=300, blank=True)
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        constraints = [models.UniqueConstraint(fields=["cycle", "code"], name="unique_document_code")]


class Application(VersionedModel):
    """One applicant's application for one place. The applicant may change it only in draft or when asked for more
    information; every submission is kept as a snapshot."""

    class Stage(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        NEEDS_INFORMATION = "needs_information", "More information needed"
        ELIGIBLE = "eligible", "Eligible"
        REJECTED = "rejected", "Not offered a place"
        OFFERED = "offered", "Place offered"
        OFFER_EXPIRED = "offer_expired", "Offer expired"
        ACCEPTED = "accepted", "Offer accepted"
        ENROLLED = "enrolled", "Enrolled"
        WITHDRAWN = "withdrawn", "Withdrawn"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="applications")
    cycle = models.ForeignKey(AdmissionCycle, on_delete=models.PROTECT, related_name="applications")
    place = models.ForeignKey(Place, on_delete=models.PROTECT, related_name="applications")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="applications")
    number = models.CharField(max_length=20, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.DRAFT)
    learner_name = models.CharField(max_length=150, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    guardian_name = models.CharField(max_length=150, blank=True)
    guardian_relationship = models.CharField(max_length=40, blank=True)
    guardian_phone = models.CharField(max_length=30, blank=True)
    guardian_email = models.EmailField(blank=True)
    address = models.TextField(max_length=500, blank=True)
    previous_school = models.CharField(max_length=200, blank=True)
    answers = models.JSONField(default=dict, blank=True)
    revision = models.PositiveIntegerField(default=0)
    information_request = models.CharField(max_length=1000, blank=True)
    decision_reason = models.CharField(max_length=500, blank=True)
    offer_expires_on = models.DateField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    # Idempotency key of the request that started it, so a retried "start" returns the same draft.
    creation_key = models.UUIDField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cycle", "number"], condition=~models.Q(number=""), name="unique_application_number"
            )
        ]

    def __str__(self) -> str:
        return self.number or f"Draft {self.pk}"


class Submission(models.Model):
    """What was submitted, as it was: kept unchanged when the applicant is asked to correct something."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="submissions")
    revision = models.PositiveIntegerField()
    snapshot = models.JSONField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-revision"]
        constraints = [models.UniqueConstraint(fields=["application", "revision"], name="unique_submission_revision")]


class Document(VersionedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Not checked yet"
        VERIFIED = "verified", "Checked"
        REJECTED = "rejected", "Needs replacing"
        REPLACED = "replaced", "Replaced"

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="documents")
    requirement = models.ForeignKey(DocumentRequirement, on_delete=models.PROTECT, related_name="+")
    file = models.FileField(storage=private_storage, upload_to=document_path)
    original_name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=40)
    size = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    review_note = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-created_at"]


class Note(models.Model):
    """Staff's internal note on an application; applicants never see these."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    text = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
