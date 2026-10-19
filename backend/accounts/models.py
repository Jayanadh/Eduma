import re
import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from accounts.roles import BUILTIN_ROLES
from common.models import VersionedModel

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")
# <institution slug>.<student number>, e.g. aster.2027-0001: made only by enrollment (slice 4a S4-07).
STUDENT_LOGIN_RE = re.compile(r"^[a-z0-9-]+\.\d{4}-\d+$")


def normalize_username(value: str) -> str:
    """Login IDs are case-insensitive: they are stored and looked up in lowercase."""
    return value.strip().lower()


def validate_username(value: str) -> str:
    username = normalize_username(value)
    if not USERNAME_RE.match(username):
        raise ValidationError("Use 3–40 lowercase letters, digits, dots, dashes or underscores.")
    if STUDENT_LOGIN_RE.match(username):
        raise ValidationError("IDs like aster.2027-0001 are kept for student logins. Choose another.")
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


class Membership(VersionedModel):
    """A user's place in one institution. What they may do there comes from its role assignments. Revoked
    memberships stay as history."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    class Kind(models.TextChoices):
        # Staff work in the institution's workspace; applicants and students have their own portals (slice 4a S4-01).
        STAFF = "staff", "Staff"
        APPLICANT = "applicant", "Applicant"
        STUDENT = "student", "Student"
        GUARDIAN = "guardian", "Guardian"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="memberships")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.STAFF)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="memberships")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["institution", "user"], name="one_membership_per_institution")]

    def __str__(self) -> str:
        return f"{self.user} in {self.institution_id}"


class Employee(VersionedModel):
    """A staff member's employment record (spec pack 08 Employee). Leave, payroll and contracts arrive with HR."""

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="employees")
    membership = models.OneToOneField(Membership, on_delete=models.PROTECT, related_name="employee")
    employee_number = models.CharField(max_length=20, blank=True)
    joined_on = models.DateField(null=True, blank=True)
    left_on = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "employee_number"],
                condition=~Q(employee_number=""),
                name="unique_employee_number",
            )
        ]


class CustomRole(VersionedModel):
    """A role an institution names itself, from the permission registry. Archived roles grant nothing."""

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="custom_roles")
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=300, blank=True)
    permissions = ArrayField(models.CharField(max_length=60), default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-is_active", "name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), "institution", condition=Q(is_active=True), name="unique_active_role_name"
            )
        ]

    def __str__(self) -> str:
        return self.name


class RoleAssignment(VersionedModel):
    """One role for one person, over the whole institution, a campus or a department, from starts_on to ends_on.
    Never edited: a change ends it and gives another, so the history shows who could do what, when."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        # Given while role-change approval is on; grants nothing until someone else approves it (slice 3 S3-08).
        PENDING = "pending", "Waiting for approval"
        ENDED = "ended", "Ended"

    class ScopeType(models.TextChoices):
        INSTITUTION = "institution", "Whole institution"
        CAMPUS = "campus", "Campus"
        DEPARTMENT = "department", "Department"

    membership = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name="assignments")
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    role_key = models.CharField(max_length=40, blank=True)
    custom_role = models.ForeignKey(
        CustomRole, null=True, blank=True, on_delete=models.PROTECT, related_name="assignments"
    )
    scope_type = models.CharField(max_length=20, choices=ScopeType.choices)
    campus = models.ForeignKey(
        "organization.Campus", null=True, blank=True, on_delete=models.PROTECT, related_name="assignments"
    )
    department = models.ForeignKey(
        "organization.Department", null=True, blank=True, on_delete=models.PROTECT, related_name="assignments"
    )
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    ended_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=300, blank=True)
    decided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["starts_on", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(role_key="") & Q(custom_role__isnull=False))
                | (~Q(role_key="") & Q(custom_role__isnull=True)),
                name="assignment_one_role",
            ),
            models.CheckConstraint(
                condition=Q(scope_type="institution", campus__isnull=True, department__isnull=True)
                | Q(scope_type="campus", campus__isnull=False, department__isnull=True)
                | Q(scope_type="department", campus__isnull=True, department__isnull=False),
                name="assignment_scope_matches",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.role_label} · {self.scope_label}"

    @property
    def permissions(self) -> frozenset[str]:
        if self.custom_role_id is None:
            role = BUILTIN_ROLES.get(self.role_key)
            return role.permissions if role else frozenset()
        return frozenset(self.custom_role.permissions) if self.custom_role.is_active else frozenset()

    @property
    def scope(self) -> tuple:
        return (self.scope_type, self.campus_id or self.department_id)

    @property
    def role_label(self) -> str:
        if self.custom_role_id is not None:
            return self.custom_role.name
        role = BUILTIN_ROLES.get(self.role_key)
        return role.label if role else self.role_key

    @property
    def scope_label(self) -> str:
        if self.campus_id:
            return self.campus.name
        if self.department_id:
            return self.department.name
        return "Whole institution"
