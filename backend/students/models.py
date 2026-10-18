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


class Student(VersionedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        WITHDRAWN = "withdrawn", "Withdrawn"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="students")
    person = models.OneToOneField(Person, on_delete=models.PROTECT, related_name="student")
    number = models.CharField(max_length=20)
    admitted_on = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
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

    class Meta:
        ordering = ["-entry_date"]
        constraints = [
            models.UniqueConstraint(fields=["student"], condition=Q(status="active"), name="one_active_enrollment")
        ]
