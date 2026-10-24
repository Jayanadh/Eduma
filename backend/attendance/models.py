"""Attendance and assignments (slice 6 S6-06..11)."""

import uuid

from django.conf import settings
from django.db import models

from common.models import VersionedModel


class AttendanceSession(VersionedModel):
    class State(models.TextChoices):
        DRAFT = "draft", "Saved, not submitted"
        SUBMITTED = "submitted", "Submitted"
        LOCKED = "locked", "Locked"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    section = models.ForeignKey("academics.Section", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    offering = models.ForeignKey(
        "academics.CourseOffering", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    slot = models.ForeignKey(
        "academics.TimetableSlot", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    date = models.DateField()
    state = models.CharField(max_length=10, choices=State.choices, default=State.DRAFT)
    taken_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["section", "date", "slot"], name="one_section_session",
                                    nulls_distinct=False, condition=models.Q(section__isnull=False)),
            models.UniqueConstraint(fields=["offering", "date", "slot"], name="one_offering_session",
                                    nulls_distinct=False, condition=models.Q(offering__isnull=False)),
            models.CheckConstraint(
                condition=models.Q(section__isnull=False, offering__isnull=True)
                | models.Q(section__isnull=True, offering__isnull=False),
                name="session_one_target",
            ),
        ]  # fmt: skip


class AttendanceMark(models.Model):
    class Code(models.TextChoices):
        PRESENT = "present", "Present"
        LATE = "late", "Late"
        ABSENT = "absent", "Absent"
        EXCUSED = "excused", "Excused"

    # Which codes count towards attendance (numerator) and which are expected sessions (denominator) — S6-06.
    NUMERATOR = ("present", "late")
    DENOMINATOR = ("present", "late", "absent")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="marks")
    enrollment = models.ForeignKey("students.Enrollment", on_delete=models.PROTECT, related_name="attendance")
    code = models.CharField(max_length=8, choices=Code.choices)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "enrollment"], name="one_mark_per_session")]


class AttendanceCorrection(models.Model):
    class State(models.TextChoices):
        REQUESTED = "requested", "Waiting for approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    mark = models.ForeignKey(AttendanceMark, on_delete=models.PROTECT, related_name="corrections")
    previous_code = models.CharField(max_length=8)
    new_code = models.CharField(max_length=8)
    reason = models.CharField(max_length=300)
    state = models.CharField(max_length=10, choices=State.choices, default=State.REQUESTED)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]


class Assignment(VersionedModel):
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    section = models.ForeignKey("academics.Section", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    offering = models.ForeignKey(
        "academics.CourseOffering", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    title = models.CharField(max_length=150)
    instructions = models.TextField(max_length=4000)
    due_at = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-due_at"]


class Submission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    enrollment = models.ForeignKey("students.Enrollment", on_delete=models.PROTECT, related_name="submissions")
    text = models.TextField(max_length=10000)
    submitted_at = models.DateTimeField()
    late = models.BooleanField(default=False)
    feedback = models.TextField(max_length=4000, blank=True)
    feedback_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    feedback_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assignment", "enrollment"], name="one_submission")]
