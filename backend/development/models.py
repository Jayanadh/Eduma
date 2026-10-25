"""Placements, internships, alumni, research and quality evidence (slice 10c S10C-05..09; SCR-048)."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from admissions.models import private_storage


def _id():
    return models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


# Placements, internships and alumni


class Employer(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=150)
    contact = models.CharField(max_length=150, blank=True)


class Opportunity(models.Model):
    class Kind(models.TextChoices):
        JOB = "job", "Job"
        INTERNSHIP = "internship", "Internship"

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    employer = models.ForeignKey(Employer, on_delete=models.PROTECT, related_name="opportunities")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    title = models.CharField(max_length=150)
    description = models.TextField(max_length=4000, blank=True)
    programs = models.ManyToManyField("academics.Program", blank=True, related_name="+")
    min_cgpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    closes_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["closes_on"]


class PlacementApplication(models.Model):
    class State(models.TextChoices):
        APPLIED = "applied", "Applied"
        SHORTLISTED = "shortlisted", "Shortlisted"
        OFFERED = "offered", "Offered"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        REJECTED = "rejected", "Not selected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = _id()
    opportunity = models.ForeignKey(Opportunity, on_delete=models.PROTECT, related_name="applications")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="placement_applications")
    consented_at = models.DateTimeField()  # consent to share the profile with this employer
    eligibility = models.JSONField()  # what was checked, as it was when applying
    state = models.CharField(max_length=12, choices=State.choices, default=State.APPLIED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["opportunity", "student"], name="one_application_each")]


class Internship(models.Model):
    id = _id()
    application = models.OneToOneField(PlacementApplication, on_delete=models.PROTECT, related_name="internship")
    supervisor = models.ForeignKey(
        "accounts.Membership", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(max_length=2000, blank=True)
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    evaluated_at = models.DateTimeField(null=True, blank=True)


class AlumniProfile(models.Model):
    id = _id()
    student = models.OneToOneField("students.Student", on_delete=models.PROTECT, related_name="alumni_profile")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    occupation = models.CharField(max_length=150, blank=True)
    consented_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)


# Research


class Scholar(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    student = models.OneToOneField("students.Student", on_delete=models.PROTECT, related_name="scholar")
    topic = models.CharField(max_length=250)
    started_on = models.DateField()


class Supervision(models.Model):
    id = _id()
    scholar = models.ForeignKey(Scholar, on_delete=models.CASCADE, related_name="supervisions")
    supervisor = models.ForeignKey("accounts.Membership", on_delete=models.PROTECT, related_name="+")
    role = models.CharField(max_length=4, default="main")  # main / co
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)


class EthicsApproval(models.Model):
    id = _id()
    scholar = models.ForeignKey(Scholar, on_delete=models.CASCADE, related_name="ethics")
    reference = models.CharField(max_length=60)
    committee = models.CharField(max_length=120)
    valid_from = models.DateField()
    valid_to = models.DateField()


class Milestone(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        RETURNED = "returned", "Returned"

    id = _id()
    scholar = models.ForeignKey(Scholar, on_delete=models.CASCADE, related_name="milestones")
    title = models.CharField(max_length=150)
    due_on = models.DateField()
    needs_ethics = models.BooleanField(default=False)
    state = models.CharField(max_length=10, choices=State.choices, default=State.PENDING)
    summary = models.TextField(max_length=4000, blank=True)
    note = models.CharField(max_length=500, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["due_on"]


# Quality evidence


class ReviewCycle(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    framework = models.CharField(max_length=60)
    period = models.CharField(max_length=30)
    frozen_at = models.DateTimeField(null=True, blank=True)
    snapshot = models.JSONField(null=True, blank=True)
    snapshot_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-period"]


class EvidenceRequest(models.Model):
    class State(models.TextChoices):
        REQUESTED = "requested", "Requested"
        SUBMITTED = "submitted", "Submitted"
        ACCEPTED = "accepted", "Accepted"
        RETURNED = "returned", "Returned"

    id = _id()
    cycle = models.ForeignKey(ReviewCycle, on_delete=models.CASCADE, related_name="requests")
    criterion = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    owner = models.ForeignKey("accounts.Membership", on_delete=models.PROTECT, related_name="+")
    state = models.CharField(max_length=10, choices=State.choices, default=State.REQUESTED)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["criterion", "title"]


def evidence_path(version, filename: str) -> str:
    return f"evidence/{version.request.cycle.institution_id}/{version.request_id}/{filename}"


class EvidenceVersion(models.Model):
    id = _id()
    request = models.ForeignKey(EvidenceRequest, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveSmallIntegerField()
    file = models.FileField(storage=private_storage, upload_to=evidence_path)
    original_name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=40)
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["request", "number"], name="unique_evidence_version"),
            models.CheckConstraint(condition=~Q(sha256=""), name="evidence_has_hash"),
        ]
