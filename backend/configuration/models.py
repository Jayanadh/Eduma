"""An institution's settings as revisions: drafted, approved where needed, published from a day, and kept after they
are replaced, so the value in force on any past day can still be read (spec pack 03 WF-CFG, slice 3 spec §3)."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from common.models import VersionedModel


class SettingRevision(VersionedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Waiting for approval"
        PUBLISHED = "published", "Published"
        SUPERSEDED = "superseded", "Replaced before it started"
        WITHDRAWN = "withdrawn", "Withdrawn"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="settings")
    # Campus overrides arrive with the first setting allowed to differ by campus (slice 3 S3-09).
    campus = models.ForeignKey("organization.Campus", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    key = models.CharField(max_length=60)
    number = models.PositiveIntegerField()
    value = models.JSONField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    effective_from = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=300, blank=True)
    return_note = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "key"], condition=Q(status__in=["draft", "pending"]), name="one_open_revision"
            ),
            models.UniqueConstraint(fields=["institution", "key", "number"], name="unique_setting_revision_number"),
        ]

    def __str__(self) -> str:
        return f"{self.key} #{self.number} ({self.status})"
