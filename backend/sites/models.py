import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from common.models import VersionedModel


def brand_path(asset: "BrandAsset", filename: str) -> str:
    # The stored name never comes from the uploader: institution folder, asset id and the detected format.
    return f"brand/{asset.institution_id}/{asset.id}.{filename.rsplit('.', 1)[-1]}"


class BrandAsset(models.Model):
    """An image for an institution's branding or public page. Re-encoded on upload; public by classification."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="brand_assets")
    file = models.FileField(upload_to=brand_path)
    content_type = models.CharField(max_length=40)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    byte_size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.institution_id}/{self.id}"


class SiteRevision(VersionedModel):
    """One version of an institution's theme and public page. At most one draft (being edited) and one published (what
    visitors see) at a time; older published versions are kept as superseded and can be restored."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        SUPERSEDED = "superseded", "Superseded"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="site_revisions")
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    primary_color = models.CharField(max_length=7)
    secondary_color = models.CharField(max_length=7)
    heading_font = models.CharField(max_length=20)
    body_font = models.CharField(max_length=20)
    logo = models.ForeignKey(BrandAsset, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    content = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["institution", "number"], name="unique_revision_number"),
            models.UniqueConstraint(fields=["institution"], condition=Q(status="draft"), name="one_draft_per_institution"),
            models.UniqueConstraint(
                fields=["institution"], condition=Q(status="published"), name="one_published_per_institution"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.institution_id} #{self.number} ({self.status})"
