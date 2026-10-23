"""A school's academic structure (slice 5a): years and terms, grades and subjects, sections with their teachers, and
each student's placement in a section for a year (the pack's EnrollmentPeriod, inside the 4a Enrollment)."""

import uuid

from django.conf import settings
from django.db import models

from common.models import VersionedModel


class AcademicYear(VersionedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        CURRENT = "current", "Current"
        CLOSED = "closed", "Closed"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="academic_years")
    code = models.CharField(max_length=20)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        ordering = ["-starts_on"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="unique_academic_year_code")]

    def __str__(self) -> str:
        return self.code


class Term(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="terms")
    name = models.CharField(max_length=40)
    ordinal = models.PositiveSmallIntegerField()
    starts_on = models.DateField()
    ends_on = models.DateField()

    class Meta:
        ordering = ["ordinal"]
        constraints = [models.UniqueConstraint(fields=["year", "ordinal"], name="unique_term_ordinal")]


class GradeLevel(VersionedModel):
    """A school grade (Class 6). Higher-education programs are a separate concept (slice 5b)."""

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="grades")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=60)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="unique_grade_code")]

    def __str__(self) -> str:
        return self.name


class Subject(VersionedModel):
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="subjects")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="unique_subject_code")]

    def __str__(self) -> str:
        return self.name


class Section(VersionedModel):
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="sections")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="sections")
    grade = models.ForeignKey(GradeLevel, on_delete=models.PROTECT, related_name="sections")
    campus = models.ForeignKey("organization.Campus", on_delete=models.PROTECT, related_name="sections")
    code = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField()
    class_teacher = models.ForeignKey(
        "accounts.Membership", null=True, blank=True, on_delete=models.PROTECT, related_name="class_sections"
    )

    class Meta:
        ordering = ["grade__order", "code"]
        constraints = [models.UniqueConstraint(fields=["year", "code"], name="unique_section_code_per_year")]

    def __str__(self) -> str:
        return self.code


class TeachingAssignment(models.Model):
    """Who teaches what in a section; a relationship that opens the section's roster to that teacher."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="teaching")
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    membership = models.ForeignKey("accounts.Membership", on_delete=models.PROTECT, related_name="teaching")
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["subject__name"]


class EnrollmentPeriod(VersionedModel):
    """A student's placement for one academic year, inside their enduring Enrollment (spec pack 08 §4)."""

    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    enrollment = models.ForeignKey("students.Enrollment", on_delete=models.PROTECT, related_name="periods")
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="placements")
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name="placements")
    grade = models.ForeignKey(GradeLevel, on_delete=models.PROTECT, related_name="+")
    campus = models.ForeignKey("organization.Campus", on_delete=models.PROTECT, related_name="+")
    state = models.CharField(max_length=8, choices=State.choices, default=State.ACTIVE)
    is_repeat = models.BooleanField(default=False)
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year__starts_on"]
        constraints = [models.UniqueConstraint(fields=["enrollment", "year"], name="one_placement_per_year")]
