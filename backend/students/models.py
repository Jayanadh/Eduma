"""Learners as the institution knows them: a Person (biographic details, owned by the institution, never merged with
another person automatically), a Student record with its number, and Enrollments for each study-track episode (spec
pack 08 §4, slice 4a spec §3)."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from common.models import VersionedModel


class Person(VersionedModel):
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="people")
    full_name = models.CharField(max_length=150)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.full_name


class StudentManager(models.Manager):
    def next_number(self, institution, start_year: int) -> str:
        """The next free number for the year: 2027-0001, 2027-0002… Call it while holding the institution's lock."""
        prefix = f"{start_year}-"
        taken = self.filter(institution=institution, number__startswith=prefix).values_list("number", flat=True)
        highest = max((int(number[len(prefix) :]) for number in taken), default=0)
        return f"{prefix}{highest + 1:04d}"

    def possible_duplicates(self, institution, name: str, date_of_birth, exclude_application=None) -> list:
        """Students here with the same name (ignoring case and spacing) and date of birth: a warning for staff, never
        a merge (spec pack 08 §4)."""
        if date_of_birth is None:
            return []
        wanted = " ".join(name.split()).lower()
        rows = self.filter(institution=institution, person__date_of_birth=date_of_birth).select_related("person")
        if exclude_application is not None:
            rows = rows.exclude(application=exclude_application)
        return [row for row in rows if " ".join(row.person.full_name.split()).lower() == wanted]


class Student(VersionedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        WITHDRAWN = "withdrawn", "Withdrawn"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="students")
    person = models.OneToOneField(Person, on_delete=models.PROTECT, related_name="student")
    number = models.CharField(max_length=20)
    admitted_on = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    left_on = models.DateField(null=True, blank=True)
    # The admission it came from (provenance), and the student's own login.
    application = models.OneToOneField(
        "admissions.Application", null=True, blank=True, on_delete=models.PROTECT, related_name="student_record"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="student_record"
    )

    objects = StudentManager()

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["institution", "number"], name="unique_student_number")]

    def __str__(self) -> str:
        return f"{self.number} {self.person.full_name}"

    @property
    def scope(self):
        """Where authority over this student must reach: the current enrollment's campus, else the whole
        institution (an accounts.permissions Scope)."""
        current = self.enrollments.filter(status="active").first()
        return ("campus", current.campus_id) if current and current.campus_id else ("institution", None)


class Enrollment(VersionedModel):
    """One study-track episode: the year and place a student was admitted to."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="enrollments")
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    academic_year = models.CharField(max_length=20)
    place_code = models.CharField(max_length=20)
    place_label = models.CharField(max_length=80)
    campus = models.ForeignKey("organization.Campus", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    entry_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    exit_date = models.DateField(null=True, blank=True)
    exit_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-entry_date"]
        constraints = [
            models.UniqueConstraint(fields=["student"], condition=Q(status="active"), name="one_active_enrollment")
        ]


class GuardianLink(VersionedModel):
    """Which adult may see which child, decided on the record by staff (slice 4b S4B-01). A proposed link grants
    nothing; an active one grants its access flags between its dates; a revoked one is history."""

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Waiting for verification"
        ACTIVE = "active", "Verified"
        REVOKED = "revoked", "Revoked"

    class Basis(models.TextChoices):
        PARENT = "parent", "Parent"
        LEGAL_GUARDIAN = "legal_guardian", "Legal guardian"
        COURT_ORDER = "court_order", "Court order"
        STUDENT_CONSENT = "student_consent", "The student's own consent"
        OTHER = "other", "Other"

    class Method(models.TextChoices):
        DOCUMENTS_IN_PERSON = "documents_in_person", "Documents seen in person"
        DOCUMENTS_ON_FILE = "documents_on_file", "Documents on file"
        COURT_ORDER = "court_order", "Court order"
        OTHER = "other", "Other"

    class Source(models.TextChoices):
        ENROLLMENT = "enrollment", "Enrollment"
        STAFF = "staff", "Staff"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="guardian_links")
    adult = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="guardian_of")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="guardian_links"
    )
    relationship = models.CharField(max_length=40)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PROPOSED)
    access_record = models.BooleanField(default=False)
    access_fees = models.BooleanField(default=False)
    access_messages = models.BooleanField(default=False)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    authority_basis = models.CharField(max_length=20, choices=Basis.choices, blank=True)
    verification_method = models.CharField(max_length=24, choices=Method.choices, blank=True)
    verification_reference = models.CharField(max_length=120, blank=True)
    restrictions = models.TextField(max_length=1000, blank=True)
    source = models.CharField(max_length=12, choices=Source.choices)
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "adult"],
                condition=Q(status__in=["proposed", "active"]),
                name="one_live_guardian_link",
            )
        ]

    def in_effect(self, today) -> bool:
        return (
            self.status == self.Status.ACTIVE
            and self.starts_on is not None
            and self.starts_on <= today
            and (self.ends_on is None or today <= self.ends_on)
        )
