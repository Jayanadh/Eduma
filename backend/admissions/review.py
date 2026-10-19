"""Staff review of applications, to an offer within the places available (slice 4a spec §4). Who may act follows the
place's campus: a campus-scoped reviewer works on that campus's places only."""

import datetime as dt

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.permissions import WHOLE, active_membership, grants, has_perm, today_for
from admissions.applications import Stage, expire_if_due, wrong_stage
from admissions.models import Application, Document, Note, Place
from common import audit
from common.exceptions import Problem

REVIEW = "application.review"
APPROVE = "admission.approve"
REVIEWABLE = (Stage.SUBMITTED, Stage.UNDER_REVIEW, Stage.NEEDS_INFORMATION, Stage.ELIGIBLE)
REJECTABLE = (*REVIEWABLE, Stage.OFFER_EXPIRED)
OFFERABLE = (Stage.ELIGIBLE, Stage.OFFER_EXPIRED)


def _scope(application: Application):
    campus = application.place.campus_id
    return ("campus", campus) if campus else WHOLE


def can_review(actor, application: Application) -> bool:
    return has_perm(actor, application.institution, REVIEW, _scope(application))


def can_approve(actor, application: Application) -> bool:
    return has_perm(actor, application.institution, APPROVE, _scope(application))


def visible(actor, institution):
    """Applications the actor may see as staff: everything with a whole-institution review or approval role, otherwise
    those for places at the campuses their roles cover. Drafts are the applicant's own business."""
    scopes = [where for perms, where in grants(active_membership(actor, institution)) if perms & {REVIEW, APPROVE}]
    found = institution.applications.exclude(stage=Stage.DRAFT)
    if WHOLE in scopes:
        return found
    return found.filter(place__campus_id__in=[pk for kind, pk in scopes if kind == "campus"])


def seats_in_use(place: Place, today: dt.date) -> int:
    """Offers not yet expired, acceptances and enrollments."""
    holding = place.applications.filter(stage__in=(Stage.ACCEPTED, Stage.ENROLLED)).count()
    offered = place.applications.filter(stage=Stage.OFFERED, offer_expires_on__gte=today).count()
    return holding + offered


def _locked(application: Application, version: int, allowed: tuple, check) -> Application:
    application = Application.objects.select_for_update().select_related("institution", "place").get(pk=application.pk)
    application.check_version(version)
    if not check(application):
        raise PermissionDenied("Your role does not cover this application.")
    if application.stage not in allowed:
        raise wrong_stage(application)
    return application


def _done(actor, application: Application, action: str, summary: str, **changes) -> Application:
    application.decided_by = actor
    application.save()
    audit.log(
        actor,
        action,
        application,
        f"{application.number}: {summary}",
        institution=application.institution,
        changes=changes,
    )
    return application


def _reviewer(actor, application):
    return can_review(actor, application)


def start_review(actor, application, version):
    with transaction.atomic():
        found = _locked(application, version, (Stage.SUBMITTED,), lambda a: _reviewer(actor, a))
        found.stage = Stage.UNDER_REVIEW
        return _done(actor, found, "application.review_started", "review started")


def request_information(actor, application, version, message: str):
    message = message.strip()
    if not message:
        raise ValidationError({"message": ["Say what the applicant needs to give or change."]})
    with transaction.atomic():
        found = _locked(application, version, (Stage.SUBMITTED, Stage.UNDER_REVIEW), lambda a: _reviewer(actor, a))
        found.stage = Stage.NEEDS_INFORMATION
        found.information_request = message
        return _done(actor, found, "application.information_requested", "more information asked for", message=message)


def mark_eligible(actor, application, version):
    with transaction.atomic():
        found = _locked(application, version, (Stage.UNDER_REVIEW,), lambda a: _reviewer(actor, a))
        found.stage = Stage.ELIGIBLE
        return _done(actor, found, "application.eligible", "marked eligible")


def reject(actor, application, version, reason: str):
    reason = reason.strip()
    if not reason:
        raise ValidationError({"reason": ["Give the reason; the applicant sees it."]})
    expire_if_due(application)
    with transaction.atomic():
        found = _locked(application, version, REJECTABLE, lambda a: _reviewer(actor, a))
        found.stage = Stage.REJECTED
        found.decision_reason = reason
        return _done(actor, found, "application.rejected", "not offered a place", reason=reason)


def offer(actor, application, version, expires_on: dt.date):
    """Offers a place if one is free. The place's row is locked so two offers cannot take the last seat."""
    today = today_for(application.institution)
    if expires_on <= today:
        raise ValidationError({"expires_on": ["Give the family at least until tomorrow to accept."]})
    expire_if_due(application)
    with transaction.atomic():
        found = _locked(application, version, OFFERABLE, lambda a: can_approve(actor, a))
        place = Place.objects.select_for_update().get(pk=found.place_id)
        if seats_in_use(place, today) >= place.seats:
            raise Problem(409, "no_seats", f"All {place.seats} places in {place.label} are offered or taken.")
        found.stage = Stage.OFFERED
        found.offer_expires_on = expires_on
        return _done(
            actor, found, "application.offered", f"place offered until {expires_on}", expires_on=str(expires_on)
        )


def review_document(actor, document: Document, version: int, verified: bool, note: str = ""):
    note = note.strip()
    if not verified and not note:
        raise ValidationError({"note": ["Say what is wrong so the family can fix it."]})
    with transaction.atomic():
        found = Document.objects.select_for_update().select_related("application__institution", "application__place")
        document = found.get(pk=document.pk)
        document.check_version(version)
        application = document.application
        if not can_review(actor, application):
            raise PermissionDenied("Your role does not cover this application.")
        if application.stage not in REVIEWABLE or document.status == Document.Status.REPLACED:
            raise Problem(409, "invalid_transition", "This document can no longer be reviewed.")
        document.status = Document.Status.VERIFIED if verified else Document.Status.REJECTED
        document.review_note = note
        document.reviewed_by = actor
        document.save()
        audit.log(
            actor,
            "application.document_verified" if verified else "application.document_rejected",
            application,
            f"{application.number}: {document.requirement.label} {'checked' if verified else 'needs replacing'}",
            institution=application.institution,
            changes={"note": note} if note else {},
        )
        return document


def add_note(actor, application, text: str) -> Note:
    text = text.strip()
    if not text:
        raise ValidationError({"text": ["Write the note."]})
    if not (can_review(actor, application) or can_approve(actor, application)):
        raise PermissionDenied("Your role does not cover this application.")
    return Note.objects.create(application=application, author=actor, text=text, created_at=timezone.now())
