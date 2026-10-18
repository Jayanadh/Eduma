import re

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from common.models import VersionedModel

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")
# Subdomains Eduma keeps for itself.
RESERVED_SLUGS = frozenset(
    {
        "www",
        "api",
        "app",
        "admin",
        "console",
        "login",
        "static",
        "media",
        "mail",
        "eduma",
        "platform",
        "help",
        "support",
        "status",
    }
)


def validate_slug(value: str) -> str:
    """An institution's subdomain: <slug>.eduma.app."""
    slug = value.strip().lower()
    if not SLUG_RE.match(slug):
        raise ValidationError(
            "Use 3–40 lowercase letters, digits or dashes, starting and ending with a letter or digit."
        )
    if slug in RESERVED_SLUGS:
        raise ValidationError("This address is reserved.")
    return slug


class Category(models.TextChoices):
    SCHOOL = "school", "School"
    COLLEGE = "college", "College"
    ENGINEERING_COLLEGE = "engineering_college", "Engineering college"
    UNIVERSITY = "university", "University"


class LifecycleStatus(models.TextChoices):
    SETUP = "setup", "Setting up"
    ACTIVE = "active", "Active"
    RESTRICTED = "restricted", "Restricted"
    SUSPENDED = "suspended", "Suspended"
    ARCHIVED = "archived", "Archived"


# Members may sign in only while their institution is being set up, active or restricted (read-only).
SIGN_IN_STATES = frozenset({LifecycleStatus.SETUP, LifecycleStatus.ACTIVE, LifecycleStatus.RESTRICTED})


class Institution(VersionedModel):
    """The tenant: every institution-owned record belongs to exactly one. Served at <slug>.<base host>, and at its
    custom domain when it has one."""

    slug = models.CharField(max_length=40, unique=True, validators=[validate_slug])
    # A domain the institution bought and pointed at Eduma, e.g. www.dps.edu.in. When set, its links use it; the
    # <slug> address keeps working.
    custom_domain = models.CharField(max_length=253, blank=True)
    legal_name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=120)
    category = models.CharField(max_length=30, choices=Category.choices)
    country_code = models.CharField(max_length=2, default="IN")
    timezone = models.CharField(max_length=60, default="Asia/Kolkata")
    base_currency = models.CharField(max_length=3, default="INR")
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    # Identifiers that apply only to some categories; strings so leading zeros survive.
    board_affiliation_code = models.CharField(max_length=40, blank=True)
    udise_code = models.CharField("UDISE+ code", max_length=20, blank=True)
    aishe_code = models.CharField("AISHE code", max_length=20, blank=True)
    lifecycle_status = models.CharField(max_length=20, choices=LifecycleStatus.choices, default=LifecycleStatus.SETUP)
    status_reason = models.CharField(max_length=500, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    # Module keys from institutions.modules that the institution's plan includes, set by the platform.
    modules = ArrayField(models.CharField(max_length=40), default=list, blank=True)
    # The onboarding request's idempotency key and a hash of its details, so a retried create returns this institution.
    creation_key = models.UUIDField(unique=True, null=True, blank=True)
    creation_hash = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["display_name"]
        constraints = [
            models.UniqueConstraint(fields=["udise_code"], condition=~Q(udise_code=""), name="unique_udise_when_set"),
            models.UniqueConstraint(fields=["aishe_code"], condition=~Q(aishe_code=""), name="unique_aishe_when_set"),
            models.UniqueConstraint(
                fields=["custom_domain"], condition=~Q(custom_domain=""), name="unique_custom_domain_when_set"
            ),
        ]

    def __str__(self) -> str:
        return self.display_name
