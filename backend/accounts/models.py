import re
import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from common.models import VersionedModel

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")


def normalize_username(value: str) -> str:
    """Login IDs are case-insensitive: they are stored and looked up in lowercase."""
    return value.strip().lower()


def validate_username(value: str) -> str:
    username = normalize_username(value)
    if not USERNAME_RE.match(username):
        raise ValidationError("Use 3–40 lowercase letters, digits, dots, dashes or underscores.")
    return username


class User(AbstractUser):
    """A sign-in identity, global across institutions. What it may do in an institution comes from its Membership there;
    platform staff have is_platform_admin and no memberships. `is_active` is the on/off switch: nobody is deleted,
    because audit events and records name them."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=20, blank=True)
    is_platform_admin = models.BooleanField(default=False)
    # Set when someone else chose the password; the owner must replace it before anything else.
    must_change_password = models.BooleanField(default=False)
    created_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.username})"

    def save(self, *args, **kwargs):
        self.username = normalize_username(self.username)
        super().save(*args, **kwargs)


class Role(models.TextChoices):
    INSTITUTION_ADMIN = "INSTITUTION_ADMIN", "Institution Admin"


class Membership(VersionedModel):
    """A user's authority in one institution. Revoked memberships stay as history."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="memberships")
    role = models.CharField(max_length=30, choices=Role.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["institution", "user"], name="one_membership_per_institution")]

    def __str__(self) -> str:
        return f"{self.user} in {self.institution_id} ({self.role})"
