"""The life of a setting change: draft, check, send for approval or publish from a day, approve or return, withdraw,
and restore an older value into a new draft (slice 3 spec §4). Each runs under a lock on the institution's row, and
every step but drafting is in the audit log."""

import datetime as dt

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.permissions import has_perm, today_for
from common import audit
from common.exceptions import Problem
from configuration.models import SettingRevision
from configuration.registry import Definition, definition, setting
from institutions.models import Institution

Status = SettingRevision.Status
OPEN = (Status.DRAFT, Status.PENDING)


def _lock(institution: Institution) -> Institution:
    return Institution.objects.select_for_update().get(pk=institution.pk)


def _open(institution, key) -> SettingRevision | None:
    return SettingRevision.objects.filter(institution=institution, key=key, status__in=OPEN).first()


def _draft(institution, key) -> SettingRevision:
    draft = SettingRevision.objects.filter(institution=institution, key=key, status=Status.DRAFT).first()
    if draft is None:
        raise Problem(
            409,
            "version_conflict",
            "This draft was sent, published or withdrawn. Reload to continue.",
            current_version=None,
        )
    return draft


def _waiting() -> Problem:
    return Problem(
        409, "change_waiting", "A change to this setting is waiting for approval. Withdraw it or wait for the decision."
    )


def _clean(found: Definition, institution, value):
    try:
        return found.clean(institution, value)
    except DjangoValidationError as error:
        raise ValidationError({"value": error.messages}) from error


def _log(actor, action: str, revision: SettingRevision, verb: str, institution, **changes) -> None:
    found = definition(revision.key)
    audit.log(
        actor,
        action,
        revision,
        f"{verb} {found.label}: {found.describe(institution, revision.value)}",
        institution=institution,
        changes={"from_day": str(revision.effective_from) if revision.effective_from else None, **changes},
    )


def _other_publishers(institution, actor) -> int:
    members = institution.memberships.filter(status="active", user__is_active=True).exclude(user=actor)
    return sum(1 for m in members.select_related("user") if has_perm(m.user, institution, "configuration.publish"))


def open_draft(institution, actor, key: str) -> SettingRevision:
    """The setting's draft, started from the value in force when there is none."""
    definition(key)
    with transaction.atomic():
        institution = _lock(institution)
        found = _open(institution, key)
        if found is not None:
            if found.status == Status.PENDING:
                raise _waiting()
            return found
        number = (institution.settings.filter(key=key).aggregate(Max("number"))["number__max"] or 0) + 1
        return SettingRevision.objects.create(
            institution=institution, key=key, number=number, value=setting(institution, key), created_by=actor
        )


def save_draft(institution, actor, key: str, version: int, value) -> SettingRevision:
    found = definition(key)
    with transaction.atomic():
        institution = _lock(institution)
        draft = _draft(institution, key)
        draft.check_version(version)
        draft.value = _clean(found, institution, value)
        draft.save()
        return draft


def _publish(revision: SettingRevision, institution, approver=None) -> None:
    """Publishes; any published change of the same setting starting on or after this one's day is cancelled, since
    this one now decides from that day. Changes that have already started stay as history."""
    institution.settings.filter(
        key=revision.key, status=Status.PUBLISHED, effective_from__gte=revision.effective_from
    ).exclude(pk=revision.pk).update(status=Status.SUPERSEDED)
    revision.status = Status.PUBLISHED
    revision.published_at = timezone.now()
    revision.approved_by = approver
    revision.save()


def submit(institution, actor, key: str, version: int, effective_from: dt.date, reason: str) -> SettingRevision:
    """Publishes from `effective_from`, or sends for approval when the setting needs it."""
    found = definition(key)
    reason = reason.strip()
    with transaction.atomic():
        institution = _lock(institution)
        draft = _draft(institution, key)
        draft.check_version(version)
        if not reason:
            raise ValidationError({"reason": ["Say why; it is kept with the change."]})
        if effective_from < today_for(institution):
            raise ValidationError({"effective_from": ["Choose today or a later day."]})
        draft.value = _clean(found, institution, draft.value)
        draft.effective_from = effective_from
        draft.reason = reason
        draft.submitted_by = actor
        draft.submitted_at = timezone.now()
        if found.needs_approval:
            if _other_publishers(institution, actor) == 0:
                raise Problem(
                    409,
                    "no_approver",
                    "This change needs someone else who can publish settings to approve it, and there is nobody else.",
                )
            draft.status = Status.PENDING
            draft.save()
            _log(actor, "setting.submitted", draft, "Sent for approval", institution, reason=reason)
            return draft
        if not has_perm(actor, institution, "configuration.publish"):
            raise PermissionDenied("Ask someone who can publish settings to publish this change.")
        _publish(draft, institution)
        _log(actor, "setting.published", draft, "Published", institution, reason=reason)
        return draft


def _pending(institution, revision_id) -> SettingRevision:
    found = institution.settings.filter(pk=revision_id).first()
    if found is None:
        raise Http404
    if found.status != Status.PENDING:
        raise Problem(409, "invalid_transition", "This change is no longer waiting for approval.")
    return found


def _decider(institution, actor, revision: SettingRevision) -> None:
    if revision.submitted_by_id == actor.id:
        raise Problem(403, "own_request", "You sent this change, so someone else must decide on it.")
    if not has_perm(actor, institution, "configuration.publish"):
        raise PermissionDenied("Only someone who can publish settings can decide on this change.")


def approve(institution, actor, revision_id, version: int) -> SettingRevision:
    """Publishes a waiting change, checking its value again first: things may have changed since it was sent."""
    with transaction.atomic():
        institution = _lock(institution)
        revision = _pending(institution, revision_id)
        revision.check_version(version)
        _decider(institution, actor, revision)
        revision.value = _clean(definition(revision.key), institution, revision.value)
        revision.effective_from = max(revision.effective_from, today_for(institution))
        _publish(revision, institution, approver=actor)
        _log(actor, "setting.approved", revision, "Approved and published", institution)
        return revision


def return_to_draft(institution, actor, revision_id, version: int, note: str) -> SettingRevision:
    note = note.strip()
    with transaction.atomic():
        institution = _lock(institution)
        revision = _pending(institution, revision_id)
        revision.check_version(version)
        _decider(institution, actor, revision)
        if not note:
            raise ValidationError({"note": ["Say what needs to change."]})
        revision.status = Status.DRAFT
        revision.return_note = note
        revision.save()
        _log(actor, "setting.returned", revision, "Returned", institution, note=note)
        return revision


def withdraw(institution, actor, key: str, version: int) -> SettingRevision:
    """Drops the open draft, or the caller's own change that is waiting for approval."""
    definition(key)
    with transaction.atomic():
        institution = _lock(institution)
        found = _open(institution, key)
        if found is None:
            raise _draft(institution, key)  # no open revision: the same "reload" answer
        found.check_version(version)
        if found.status == Status.PENDING and found.submitted_by_id != actor.id:
            raise PermissionDenied("Only the person who sent this change can withdraw it.")
        was_pending = found.status == Status.PENDING
        found.status = Status.WITHDRAWN
        found.save()
        if was_pending:
            _log(actor, "setting.withdrawn", found, "Withdrew", institution)
        return found


def restore(institution, actor, key: str, revision_id, version: int | None) -> SettingRevision:
    """An earlier revision's value, into the draft (started if there is none). Publishing it is a separate step."""
    found = definition(key)
    with transaction.atomic():
        institution = _lock(institution)
        source = institution.settings.filter(pk=revision_id, key=key).exclude(status__in=OPEN).first()
        if source is None:
            raise Http404
        draft = _open(institution, key)
        if draft is not None and draft.status == Status.PENDING:
            raise _waiting()
        if draft is not None:
            draft.check_version(version)
        else:
            number = (institution.settings.filter(key=key).aggregate(Max("number"))["number__max"] or 0) + 1
            draft = SettingRevision(institution=institution, key=key, number=number, created_by=actor)
        draft.value = _clean(found, institution, source.value)
        draft.save()
        _log(actor, "setting.restored", draft, f"Restored version {source.number} of", institution)
        return draft
