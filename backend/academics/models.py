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
    # A school section names a grade; a college batch names a program (slice 5b S5B-06). Exactly one.
    grade = models.ForeignKey(GradeLevel, null=True, blank=True, on_delete=models.PROTECT, related_name="sections")
    program = models.ForeignKey("Program", null=True, blank=True, on_delete=models.PROTECT, related_name="sections")
    campus = models.ForeignKey("organization.Campus", on_delete=models.PROTECT, related_name="sections")
    code = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField()

    class Meta:
        ordering = ["grade__order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["year", "code"], name="unique_section_code_per_year"),
            models.CheckConstraint(
                condition=models.Q(grade__isnull=False, program__isnull=True)
                | models.Q(grade__isnull=True, program__isnull=False),
                name="section_grade_or_program",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class TeachingAssignment(models.Model):
    """Who teaches what in a section; a relationship that opens the section's roster to that teacher."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # A section (class or batch) or a course offering (slice 5b S5B-05). Exactly one.
    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.CASCADE, related_name="teaching")
    offering = models.ForeignKey(
        "CourseOffering", null=True, blank=True, on_delete=models.CASCADE, related_name="teaching"
    )
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    membership = models.ForeignKey("accounts.Membership", on_delete=models.PROTECT, related_name="teaching")
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["subject__name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(section__isnull=False, offering__isnull=True)
                | models.Q(section__isnull=True, offering__isnull=False),
                name="teaching_one_target",
            )
        ]


class EnrollmentPeriod(VersionedModel):
    """A student's placement for one academic year, inside their enduring Enrollment (spec pack 08 §4)."""

    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    class EndedBecause(models.TextChoices):
        NOT_ENDED = "", "—"
        TAKEN_OUT = "taken_out", "Taken out of the class"
        WITHDRAWN = "withdrawn", "Withdrawn"

    enrollment = models.ForeignKey("students.Enrollment", on_delete=models.PROTECT, related_name="periods")
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="placements")
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name="placements")
    grade = models.ForeignKey(GradeLevel, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    program = models.ForeignKey("Program", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    campus = models.ForeignKey("organization.Campus", on_delete=models.PROTECT, related_name="+")
    state = models.CharField(max_length=8, choices=State.choices, default=State.ACTIVE)
    # Why it ended: a withdrawal is undone by reinstating; a student taken out can be placed again this year.
    ended_because = models.CharField(max_length=10, choices=EndedBecause.choices, blank=True, default="")
    is_repeat = models.BooleanField(default=False)
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year__starts_on"]
        constraints = [models.UniqueConstraint(fields=["enrollment", "year"], name="one_placement_per_year")]


class Program(VersionedModel):
    """A higher-education program (B.Sc Physics): a separate concept from a school grade (slice 5b S5B-01)."""

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="programs")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    qualification = models.CharField(max_length=40)
    department = models.ForeignKey(
        "organization.Department", null=True, blank=True, on_delete=models.PROTECT, related_name="programs"
    )
    length_terms = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="unique_program_code")]

    def __str__(self) -> str:
        return self.name


class CurriculumVersion(VersionedModel):
    """A regulation a cohort follows. Published versions never change; a change is a new revision (S5B-02)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="curricula")
    regulation = models.CharField(max_length=20)
    revision = models.PositiveSmallIntegerField()
    cohort = models.PositiveSmallIntegerField()
    credits_required = models.DecimalField(max_digits=6, decimal_places=1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-cohort", "regulation", "-revision"]
        constraints = [
            models.UniqueConstraint(fields=["program", "regulation", "revision"], name="unique_curriculum_revision")
        ]

    def __str__(self) -> str:
        return f"{self.regulation} rev {self.revision}"


class Course(VersionedModel):
    class Kind(models.TextChoices):
        THEORY = "theory", "Theory"
        LAB = "lab", "Lab"
        PROJECT = "project", "Project"
        TUTORIAL = "tutorial", "Tutorial"
        OTHER = "other", "Other"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="courses")
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=150)
    credits = models.DecimalField(max_digits=4, decimal_places=1)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    department = models.ForeignKey(
        "organization.Department", null=True, blank=True, on_delete=models.PROTECT, related_name="courses"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="unique_course_code")]

    def __str__(self) -> str:
        return f"{self.code} {self.title}"


class CurriculumCourse(models.Model):
    class Category(models.TextChoices):
        CORE = "core", "Core"
        ELECTIVE = "elective", "Elective"
        OPEN_ELECTIVE = "open_elective", "Open elective"
        LAB = "lab", "Lab"
        PROJECT = "project", "Project"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    curriculum = models.ForeignKey(CurriculumVersion, on_delete=models.CASCADE, related_name="courses")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="+")
    category = models.CharField(max_length=14, choices=Category.choices)
    term = models.PositiveSmallIntegerField()
    elective_group = models.CharField(max_length=40, blank=True)
    prerequisites = models.ManyToManyField(Course, blank=True, related_name="+")

    class Meta:
        ordering = ["term", "course__code"]
        constraints = [models.UniqueConstraint(fields=["curriculum", "course"], name="one_course_per_curriculum")]


class CourseOffering(VersionedModel):
    """A course taught in a term: a section code, seats, and optionally the offering it is linked to (a lab to its
    lecture)."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="offerings")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="offerings")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="offerings")
    campus = models.ForeignKey("organization.Campus", on_delete=models.PROTECT, related_name="+")
    code = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    linked_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="linked")

    class Meta:
        ordering = ["course__code", "code"]
        constraints = [models.UniqueConstraint(fields=["course", "term", "code"], name="unique_offering_code_per_term")]

    def __str__(self) -> str:
        return f"{self.course.code}-{self.code}"
