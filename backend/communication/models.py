"""Conversations, notifications, calls and teacher-led classes (slice 9 S9-01..09)."""

import uuid

from django.conf import settings
from django.db import models


def _id():
    return models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class Policy(models.Model):
    id = _id()
    institution = models.OneToOneField("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    guardians_can_start = models.BooleanField(default=True)
    calls_enabled = models.BooleanField(default=True)
    classes_enabled = models.BooleanField(default=True)
    quiet_from = models.TimeField(null=True, blank=True)
    quiet_until = models.TimeField(null=True, blank=True)


class MediaConfig(models.Model):
    """The audio/video provider. Only a test-mode sandbox exists (D-12): it issues tokens, carries no media."""

    id = _id()
    institution = models.OneToOneField("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    provider = models.CharField(max_length=20, default="sandbox")
    secret = models.CharField(max_length=80)


class Conversation(models.Model):
    class Kind(models.TextChoices):
        STAFF = "staff", "Staff"
        FAMILY = "family", "About a student"

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="conversations"
    )
    subject = models.CharField(max_length=150)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    last_sequence = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]


class Participant(models.Model):
    id = _id()
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    role = models.CharField(max_length=10)  # staff / teacher / guardian
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    sees_from = models.PositiveIntegerField(default=1)  # the first message number this participant may read
    last_read = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["conversation", "user"], name="one_participant")]


class Message(models.Model):
    id = _id()
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    sequence = models.PositiveIntegerField()
    client_message_id = models.CharField(max_length=64)
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(fields=["conversation", "sequence"], name="unique_message_sequence"),
            models.UniqueConstraint(fields=["sender", "client_message_id"], name="unique_client_message"),
        ]


class Preference(models.Model):
    id = _id()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    quiet_from = models.TimeField(null=True, blank=True)
    quiet_until = models.TimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "institution"], name="one_preference")]


class Notification(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    text = models.CharField(max_length=200)
    link = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deliver_after = models.DateTimeField()
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Call(models.Model):
    class State(models.TextChoices):
        RINGING = "ringing", "Ringing"
        CONNECTED = "connected", "Connected"
        DECLINED = "declined", "Declined"
        CANCELED = "canceled", "Canceled"
        MISSED = "missed", "Missed"
        FAILED = "failed", "Failed"
        ENDED = "ended", "Ended"

    FINAL = ("declined", "canceled", "missed", "failed", "ended")

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    conversation = models.ForeignKey(
        Conversation, null=True, blank=True, on_delete=models.PROTECT, related_name="calls"
    )
    caller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    callee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    state = models.CharField(max_length=10, choices=State.choices, default=State.RINGING)
    reason = models.CharField(max_length=60, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)


class ClassSession(models.Model):
    class State(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        PAUSED = "paused", "Paused — waiting for the teacher"
        ENDED = "ended", "Ended"

    GRACE_SECONDS = 60

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    section = models.ForeignKey("academics.Section", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    offering = models.ForeignKey(
        "academics.CourseOffering", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    title = models.CharField(max_length=150)
    starts_at = models.DateTimeField()
    state = models.CharField(max_length=10, choices=State.choices, default=State.SCHEDULED)
    paused_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-starts_at"]


class ClassParticipant(models.Model):
    class Admission(models.TextChoices):
        WAITING = "waiting", "Waiting to be let in"
        ADMITTED = "admitted", "In the class"
        REMOVED = "removed", "Removed"

    id = _id()
    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    role = models.CharField(max_length=8)  # host / attendee
    admission = models.CharField(max_length=10, choices=Admission.choices, default=Admission.WAITING)
    token_version = models.PositiveIntegerField(default=1)
    joined_at = models.DateTimeField(null=True, blank=True)  # the current stay, while present
    seconds = models.PositiveIntegerField(default=0)  # completed stays, never double-counted

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "user"], name="one_class_participant")]
