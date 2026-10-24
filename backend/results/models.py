"""Assessments, results, documents and outcomes (slice 7 S7-01..12)."""

import uuid

from django.conf import settings
from django.db import models

from common.models import VersionedModel


class Scheme(VersionedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    family = models.UUIDField(default=uuid.uuid4)  # every revision of one scheme shares it
    revision = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    pass_percent = models.DecimalField(max_digits=5, decimal_places=2, default=40)
    decimals = models.PositiveSmallIntegerField(default=2)
    # [{"min": "90", "grade": "A+", "point": "10"}, …], highest first
    bands = models.JSONField(default=list)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name", "-revision"]
        constraints = [models.UniqueConstraint(fields=["family", "revision"], name="unique_scheme_revision")]


class SchemeComponent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheme = models.ForeignKey(Scheme, on_delete=models.CASCADE, related_name="components")
    name = models.CharField(max_length=80)
    max_marks = models.DecimalField(max_digits=6, decimal_places=2)
    weight = models.DecimalField(max_digits=5, decimal_places=2)
    min_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]


class Assessment(VersionedModel):
    class State(models.TextChoices):
        DRAFT = "draft", "Marks being entered"
        SUBMITTED = "submitted", "Waiting for moderation"
        MODERATED = "moderated", "Moderated, ready to publish"
        PUBLISHED = "published", "Published"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    scheme = models.ForeignKey(Scheme, on_delete=models.PROTECT, related_name="assessments")
    term = models.ForeignKey("academics.Term", on_delete=models.PROTECT, related_name="+")
    section = models.ForeignKey("academics.Section", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    subject = models.ForeignKey("academics.Subject", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    offering = models.ForeignKey(
        "academics.CourseOffering", null=True, blank=True, on_delete=models.PROTECT, related_name="assessments"
    )
    title = models.CharField(max_length=120)
    state = models.CharField(max_length=10, choices=State.choices, default=State.DRAFT)
    returned_reason = models.CharField(max_length=300, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-created_at"]


class Candidate(models.Model):
    """A student on the assessment's roster, snapshotted when it was created."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="candidates")
    enrollment = models.ForeignKey("students.Enrollment", on_delete=models.PROTECT, related_name="candidacies")
    registration = models.ForeignKey(
        "academics.CourseRegistration", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assessment", "enrollment"], name="one_candidate")]


class Mark(models.Model):
    class Status(models.TextChoices):
        SCORED = "scored", "Scored"
        ABSENT = "absent", "Absent"
        EXEMPT = "exempt", "Exempt"
        WITHHELD = "withheld", "Withheld"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="marks")
    component = models.ForeignKey(SchemeComponent, on_delete=models.PROTECT, related_name="+")
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.SCORED)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    entered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["candidate", "component"], name="one_mark_per_component")]


class ResultVersion(models.Model):
    """A published result. Never changed: a correction adds the next revision and supersedes this one."""

    class Outcome(models.TextChoices):
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        ABSENT = "absent", "Absent"
        WITHHELD = "withheld", "Withheld"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT, related_name="results")
    revision = models.PositiveSmallIntegerField()
    total = models.DecimalField(max_digits=14, decimal_places=8, null=True, blank=True)
    shown_total = models.CharField(max_length=20, blank=True)
    grade = models.CharField(max_length=10, blank=True)
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    outcome = models.CharField(max_length=8, choices=Outcome.choices)
    failed_components = models.JSONField(default=list)
    inputs = models.JSONField(default=dict)
    inputs_hash = models.CharField(max_length=64)
    scheme_revision = models.PositiveSmallIntegerField()
    reason = models.CharField(max_length=300, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    published_at = models.DateTimeField()
    superseded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["revision"]
        constraints = [models.UniqueConstraint(fields=["candidate", "revision"], name="unique_result_revision")]


class RevisionCase(models.Model):
    class State(models.TextChoices):
        REQUESTED = "requested", "Waiting for approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT, related_name="cases")
    reason = models.CharField(max_length=300)
    marks = models.JSONField()  # {component id: {"score": "…", "status": "…"}}
    state = models.CharField(max_length=10, choices=State.choices, default=State.REQUESTED)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)


class PromotionDecision(models.Model):
    class Decision(models.TextChoices):
        PROMOTE = "promote", "Promoted"
        REPEAT = "repeat", "Repeats the year"
        HOLD = "hold", "Decision held"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey("students.Enrollment", on_delete=models.PROTECT, related_name="promotions")
    year = models.ForeignKey("academics.AcademicYear", on_delete=models.PROTECT, related_name="+")
    decision = models.CharField(max_length=8, choices=Decision.choices)
    reason = models.CharField(max_length=300, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["enrollment", "year"], name="one_promotion_per_year")]


class IssuedDocument(models.Model):
    """A report card, transcript or award as issued: its content is frozen, hashed and verifiable."""

    class Kind(models.TextChoices):
        REPORT_CARD = "report_card", "Report card"
        TRANSCRIPT = "transcript", "Transcript"
        AWARD = "award", "Award"

    class Status(models.TextChoices):
        CURRENT = "current", "Current"
        SUPERSEDED = "superseded", "Superseded"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="documents"
    )
    holder_name = models.CharField(max_length=150)
    number = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    # What the document says, frozen at issue (S7-10): reissuing makes a new document.
    content = models.JSONField()
    content_hash = models.CharField(max_length=64)
    token = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CURRENT)
    reason = models.CharField(max_length=300, blank=True)
    supersedes = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="superseded_by"
    )
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        constraints = [models.UniqueConstraint(fields=["institution", "number"], name="unique_document_number")]


class CourseOutcome(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey("academics.Course", on_delete=models.PROTECT, related_name="outcomes")
    code = models.CharField(max_length=10)
    description = models.CharField(max_length=300)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["course", "code"], name="unique_outcome_code")]


class OutcomeMapping(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="mappings")
    component = models.ForeignKey(SchemeComponent, on_delete=models.PROTECT, related_name="+")
    outcome = models.ForeignKey(CourseOutcome, on_delete=models.PROTECT, related_name="mappings")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assessment", "component", "outcome"], name="unique_mapping")]


class AttainmentRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name="attainment_runs")
    threshold_percent = models.DecimalField(max_digits=5, decimal_places=2)
    results = models.JSONField()
    inputs_hash = models.CharField(max_length=64)
    run_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    run_at = models.DateTimeField(auto_now_add=True)
