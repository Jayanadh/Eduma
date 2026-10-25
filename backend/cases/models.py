"""Service requests and grievances: one case aggregate, confidential by type (slice 10c S10C-01..04)."""

import uuid

from django.conf import settings
from django.db import models


def _id():
    return models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class ServiceCase(models.Model):
    class Type(models.TextChoices):
        SERVICE = "service_request", "Service request"
        GRIEVANCE = "grievance", "Academic grievance"
        COUNSELLING = "counselling", "Counselling"
        SAFEGUARDING = "safeguarding", "Safeguarding"

    class State(models.TextChoices):
        SUBMITTED = "submitted", "Received"
        ASSIGNED = "assigned", "Being looked at"
        RESOLVED = "resolved", "Resolved"
        APPEALED = "appealed", "Appeal received"

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    number = models.CharField(max_length=12)
    case_type = models.CharField(max_length=15, choices=Type.choices)
    confidential = models.BooleanField()
    subject = models.CharField(max_length=150)
    description = models.TextField(max_length=4000)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    assignee = models.ForeignKey(
        "accounts.Membership", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    state = models.CharField(max_length=10, choices=State.choices, default=State.SUBMITTED)
    due_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["institution", "number"], name="unique_case_number")]


class CaseNote(models.Model):
    class Visibility(models.TextChoices):
        REQUESTER = "requester_visible", "Seen by the requester"
        INTERNAL = "internal", "Internal"

    id = _id()
    case = models.ForeignKey(ServiceCase, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    visibility = models.CharField(max_length=20, choices=Visibility.choices)
    text = models.TextField(max_length=4000)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at"]


class CaseAssignment(models.Model):
    """Who held the case and when: the history, not the access (only the current assignee has that)."""

    id = _id()
    case = models.ForeignKey(ServiceCase, on_delete=models.CASCADE, related_name="assignments")
    assignee = models.ForeignKey("accounts.Membership", on_delete=models.PROTECT, related_name="+")
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    at = models.DateTimeField(auto_now_add=True)


class Resolution(models.Model):
    id = _id()
    case = models.ForeignKey(ServiceCase, on_delete=models.CASCADE, related_name="resolutions")
    stage = models.CharField(max_length=10)  # original / appeal
    text = models.TextField(max_length=4000)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at"]


class Appeal(models.Model):
    id = _id()
    case = models.OneToOneField(ServiceCase, on_delete=models.CASCADE, related_name="appeal")
    reason = models.TextField(max_length=4000)
    at = models.DateTimeField(auto_now_add=True)
