from rest_framework import serializers

from accounts.permissions import has_perm, today_for
from configuration.models import SettingRevision
from configuration.registry import DEFINITIONS, definition, setting
from institutions.modules import MODULES

OPEN = (SettingRevision.Status.DRAFT, SettingRevision.Status.PENDING)


class DraftInput(serializers.Serializer):
    version = serializers.IntegerField()
    value = serializers.JSONField()


class SubmitInput(serializers.Serializer):
    version = serializers.IntegerField()
    effective_from = serializers.DateField()
    reason = serializers.CharField(max_length=300, allow_blank=True)


class VersionInput(serializers.Serializer):
    version = serializers.IntegerField()


class ReturnInput(VersionInput):
    note = serializers.CharField(max_length=300, allow_blank=True)


class RestoreInput(serializers.Serializer):
    """The open draft's version, when there is one to replace."""

    version = serializers.IntegerField(required=False, allow_null=True, default=None)


def _name(user) -> str | None:
    return user.full_name if user else None


def revision_item(revision: SettingRevision, viewer) -> dict:
    institution = revision.institution
    found = definition(revision.key)
    return {
        "id": str(revision.id),
        "number": revision.number,
        "status": revision.status,
        "version": revision.version,
        "value": revision.value,
        "description": found.describe(institution, revision.value),
        "effective_from": revision.effective_from,
        "reason": revision.reason,
        "return_note": revision.return_note,
        "created_by_name": _name(revision.created_by),
        "submitted_by_name": _name(revision.submitted_by),
        "submitted_at": revision.submitted_at,
        "approved_by_name": _name(revision.approved_by),
        "published_at": revision.published_at,
        "mine": revision.submitted_by_id == viewer.id,
        "can_approve": revision.status == SettingRevision.Status.PENDING
        and revision.submitted_by_id != viewer.id
        and has_perm(viewer, institution, "configuration.publish"),
    }


def _revisions(institution, key):
    return institution.settings.filter(key=key).select_related(
        "institution", "created_by", "submitted_by", "approved_by"
    )


def summary(institution, key: str, viewer) -> dict:
    found = definition(key)
    today = today_for(institution)
    value_now = setting(institution, key)
    revisions = _revisions(institution, key)
    upcoming = (
        revisions.filter(status=SettingRevision.Status.PUBLISHED, effective_from__gt=today)
        .order_by("effective_from", "number")
        .first()
    )
    open_one = revisions.filter(status__in=OPEN).first()
    return {
        "key": key,
        "label": found.label,
        "help": found.help,
        "kind": found.kind,
        "needs_approval": found.needs_approval,
        "value_now": value_now,
        "description_now": found.describe(institution, value_now),
        "scheduled": {
            "effective_from": upcoming.effective_from,
            "description": found.describe(institution, upcoming.value),
        }
        if upcoming
        else None,
        "open": {"id": str(open_one.id), "status": open_one.status, "version": open_one.version} if open_one else None,
    }


def detail(institution, key: str, viewer, history: dict) -> dict:
    found = definition(key)
    body = summary(institution, key, viewer)
    open_one = _revisions(institution, key).filter(status__in=OPEN).first()
    item = revision_item(open_one, viewer) if open_one else None
    body["draft"] = item if open_one and open_one.status == SettingRevision.Status.DRAFT else None
    body["pending"] = item if open_one and open_one.status == SettingRevision.Status.PENDING else None
    starts = (open_one and open_one.effective_from) or today_for(institution)
    body["preview"] = found.preview(institution, body["value_now"], open_one.value, starts) if open_one else []
    body["choices"] = (
        [
            {
                "key": key_,
                "label": MODULES[key_].label,
                "group": MODULES[key_].group,
                "depends_on": list(MODULES[key_].depends_on),
            }
            for key_ in sorted(institution.modules)
        ]
        if found.kind == "modules"
        else []
    )
    body["history"] = history
    return body


def history_queryset(institution, key: str):
    return _revisions(institution, key).exclude(status__in=OPEN)


KEYS = list(DEFINITIONS)
