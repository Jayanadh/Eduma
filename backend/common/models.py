import uuid

from django.conf import settings
from django.db import models

from common.exceptions import VersionConflict


class VersionedModel(models.Model):
    """UUID id, timestamps and an integer version that goes up on every save. Edits send the version they started from;
    check_version() refuses a stale one, so nobody silently overwrites someone else's newer change."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            self.version += 1
            if (fields := kwargs.get("update_fields")) is not None:
                kwargs["update_fields"] = list({*fields, "version", "updated_at"})
        super().save(*args, **kwargs)

    def check_version(self, supplied: int | None) -> None:
        if supplied != self.version:
            raise VersionConflict(self.version)


class AuditEvent(models.Model):
    """Something security-relevant that happened: who, what, to which record, when. Append-only: there is no API to
    change or delete one. Never holds passwords; `changes` names fields with safe before/after values."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    institution = models.ForeignKey(
        "institutions.Institution", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    action = models.CharField(max_length=60)
    object_type = models.CharField(max_length=40)
    object_id = models.CharField(max_length=40)
    summary = models.CharField(max_length=255)
    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self) -> str:
        return f"{self.action} {self.object_type}#{self.object_id}"
