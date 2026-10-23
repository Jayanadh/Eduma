"""Enquiries (slice 4c S4C-01 to S4C-04): asked by a family on the Apply page or recorded by staff, followed up, linked
to an application or closed. Who may answer follows the interested place's campus, like applications."""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from accounts.permissions import WHOLE, active_membership, grants, has_perm, today_for
from admissions.models import AdmissionCycle, Enquiry, FollowUp, Place
from common import audit
from common.exceptions import Problem
from institutions.models import Institution

MANAGE = "enquiry.manage"
OPEN = (Enquiry.Status.OPEN, Enquiry.Status.FOLLOWING_UP)


def scope_of(enquiry: Enquiry):
    campus = enquiry.place.campus_id if enquiry.place_id else None
    return ("campus", campus) if campus else WHOLE


def can_manage(actor, enquiry: Enquiry) -> bool:
    return has_perm(actor, enquiry.institution, MANAGE, scope_of(enquiry))


def visible(actor, institution):
    scopes = [where for perms, where in grants(active_membership(actor, institution)) if MANAGE in perms]
    found = institution.enquiries.select_related("place__campus", "assigned_to", "application", "institution")
    if WHOLE in scopes:
        return found
    return found.filter(place__campus_id__in=[pk for kind, pk in scopes if kind == "campus"])


def _place(institution, place_id, public: bool):
    if not place_id:
        return None
    # A draft cycle's places are replaced every time it is saved, so enquiries point at published or closed ones.
    cycles = AdmissionCycle.objects.filter(institution=institution).exclude(status=AdmissionCycle.Status.DRAFT)
    cycles = cycles.filter(status=AdmissionCycle.Status.PUBLISHED) if public else cycles
    place = Place.objects.filter(pk=place_id, cycle__in=cycles).select_related("campus").first()
    if place is None:
        raise ValidationError({"place": ["Choose one of this school's places."]})
    return place


def _covers(user, institution, place) -> bool:
    campus = place.campus_id if place is not None else None
    return has_perm(user, institution, MANAGE, ("campus", campus) if campus else WHOLE)


def create(institution, data: dict, source: str, actor=None) -> Enquiry:
    if not (data.get("phone") or data.get("email")):
        raise ValidationError({"phone": ["Give a phone number or an email so the school can reply."]})
    place = _place(institution, data.get("place"), public=actor is None)
    if actor is not None and not _covers(actor, institution, place):
        raise ValidationError({"place": ["Choose a place on a campus your role covers."]})
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=institution.pk)  # numbers are handed out one at a time
        enquiry = Enquiry.objects.create(
            institution=institution,
            number=Enquiry.objects.next_number(institution, today_for(institution).year),
            contact_name=data["contact_name"],
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            learner_name=data.get("learner_name", ""),
            learner_date_of_birth=data.get("learner_date_of_birth"),
            place=place,
            message=data.get("message", ""),
            source=source,
            created_by=actor,
        )
        audit.log(
            actor,
            "enquiry.created",
            enquiry,
            f"{enquiry.number} from {enquiry.contact_name} ({enquiry.get_source_display().lower()})",
            institution=institution,
        )
        return enquiry


def _locked(actor, enquiry: Enquiry, version: int) -> Enquiry:
    if not can_manage(actor, enquiry):
        raise PermissionDenied("Your role does not cover this enquiry.")
    enquiry = Enquiry.objects.select_for_update(of=("self",)).select_related("institution", "place").get(pk=enquiry.pk)
    enquiry.check_version(version)
    return enquiry


def _still_open(enquiry: Enquiry) -> None:
    if enquiry.status not in OPEN:
        raise Problem(409, "invalid_transition", f"This enquiry is {enquiry.get_status_display().lower()}.")


def update(actor, enquiry: Enquiry, version: int, data: dict) -> Enquiry:
    with transaction.atomic():
        enquiry = _locked(actor, enquiry, version)
        institution = enquiry.institution
        if "place" in data:
            enquiry.place = _place(institution, data["place"], public=False)
            if not _covers(actor, institution, enquiry.place):
                raise ValidationError({"place": ["Choose a place on a campus your role covers."]})
        if "assigned_to" in data:
            assignee = data["assigned_to"]
            enquiry.assigned_to = User.objects.filter(pk=assignee).first() if assignee is not None else None
            if assignee is not None and enquiry.assigned_to is None:
                raise ValidationError({"assigned_to": ["Choose someone whose role answers enquiries here."]})
        # Checked against the place as it now is: an assignee must be able to see the enquiry they answer.
        if enquiry.assigned_to is not None and not _covers(enquiry.assigned_to, institution, enquiry.place):
            raise ValidationError({"assigned_to": ["Choose someone whose role answers enquiries for this place."]})
        for name in ("contact_name", "phone", "email", "learner_name", "learner_date_of_birth", "next_follow_up_on"):
            if name in data:
                setattr(enquiry, name, data[name])
        enquiry.save()
        return enquiry


def add_follow_up(actor, enquiry: Enquiry, data: dict) -> Enquiry:
    note = data["note"].strip()
    if not note:
        raise ValidationError({"note": ["Write what happened."]})
    with transaction.atomic():
        enquiry = _locked(actor, enquiry, enquiry.version)
        _still_open(enquiry)
        FollowUp.objects.create(
            enquiry=enquiry, author=actor, how=data["how"], note=note, next_follow_up_on=data.get("next_follow_up_on")
        )
        enquiry.status = Enquiry.Status.FOLLOWING_UP
        enquiry.next_follow_up_on = data.get("next_follow_up_on")
        enquiry.save()
        return enquiry


def convert(actor, enquiry: Enquiry, version: int, application_number: str) -> Enquiry:
    with transaction.atomic():
        enquiry = _locked(actor, enquiry, version)
        _still_open(enquiry)
        application = enquiry.institution.applications.filter(number=application_number.strip().upper()).first()
        if application is None:
            raise ValidationError({"application_number": ["No application here has that number."]})
        enquiry.application, enquiry.status, enquiry.next_follow_up_on = application, Enquiry.Status.CONVERTED, None
        enquiry.save()
        audit.log(actor, "enquiry.converted", enquiry, f"{enquiry.number} applied as {application.number}")
        return enquiry


def close(actor, enquiry: Enquiry, version: int, reason: str) -> Enquiry:
    reason = reason.strip()
    if not reason:
        raise ValidationError({"reason": ["Say why it is closed."]})
    with transaction.atomic():
        enquiry = _locked(actor, enquiry, version)
        _still_open(enquiry)
        enquiry.status, enquiry.close_reason, enquiry.next_follow_up_on = Enquiry.Status.CLOSED, reason, None
        enquiry.save()
        audit.log(actor, "enquiry.closed", enquiry, f"{enquiry.number} closed", changes={"reason": reason})
        return enquiry


def reopen(actor, enquiry: Enquiry, version: int) -> Enquiry:
    with transaction.atomic():
        enquiry = _locked(actor, enquiry, version)
        if enquiry.status != Enquiry.Status.CLOSED:
            raise Problem(409, "invalid_transition", "Only a closed enquiry can be reopened.")
        enquiry.status, enquiry.close_reason = Enquiry.Status.OPEN, ""
        enquiry.save()
        audit.log(actor, "enquiry.reopened", enquiry, f"{enquiry.number} reopened")
        return enquiry


def due(queryset, institution):
    return queryset.filter(status__in=OPEN, next_follow_up_on__lte=today_for(institution))


def enquiry_item(enquiry: Enquiry, full: bool = False) -> dict:
    def person(user):
        return {"id": str(user.id), "full_name": user.full_name} if user else None

    item = {
        "id": str(enquiry.id),
        "version": enquiry.version,
        "number": enquiry.number,
        "contact_name": enquiry.contact_name,
        "phone": enquiry.phone,
        "email": enquiry.email,
        "learner_name": enquiry.learner_name,
        "learner_date_of_birth": enquiry.learner_date_of_birth,
        "place": {"id": str(enquiry.place.id), "label": enquiry.place.label} if enquiry.place_id else None,
        "message": enquiry.message,
        "source": enquiry.source,
        "source_label": enquiry.get_source_display(),
        "status": enquiry.status,
        "status_label": enquiry.get_status_display(),
        "close_reason": enquiry.close_reason,
        "assigned_to": person(enquiry.assigned_to),
        "next_follow_up_on": enquiry.next_follow_up_on,
        "application": {"id": str(enquiry.application.id), "number": enquiry.application.number}
        if enquiry.application_id
        else None,
        "created_at": enquiry.created_at,
        "created_by": person(enquiry.created_by),
    }
    if full:
        item["follow_ups"] = [
            {
                "how": row.how,
                "how_label": row.get_how_display(),
                "note": row.note,
                "at": row.at,
                "author": row.author.full_name,
                "next_follow_up_on": row.next_follow_up_on,
            }
            for row in enquiry.follow_ups.select_related("author")
        ]
    return item
