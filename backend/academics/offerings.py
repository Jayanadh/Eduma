"""Course offerings — a course taught in a term (slice 5b S5B-05, S5B-08): managed at the course's department, or at
the offering's campus when the course has none."""

import datetime as dt

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.models import AcademicYear, CourseOffering, TeachingAssignment, Term
from academics.sections import _staff, in_effect
from academics.structure import MANAGE
from accounts.permissions import has_perm, today_for
from common import audit
from common.exceptions import Problem

# planned → open → closed; either of the first two may be cancelled.
FORWARD = {("planned", "open"), ("open", "closed"), ("planned", "cancelled"), ("open", "cancelled")}


def can_manage(actor, offering: CourseOffering) -> bool:
    course = offering.course
    scope = ("department", course.department_id) if course.department_id else ("campus", offering.campus_id)
    return has_perm(actor, offering.institution, MANAGE, scope)


def _require(actor, offering: CourseOffering) -> None:
    if not can_manage(actor, offering):
        raise PermissionDenied("Your role does not cover this course's department or this campus.")


def _open(term: Term) -> None:
    if term.year.status == AcademicYear.Status.CLOSED:
        raise Problem(409, "year_closed", f"{term.year.code} is closed; its offerings can't change.")


def label(offering: CourseOffering) -> str:
    return f"{offering.course.code}-{offering.code}"


def _link(institution, offering: CourseOffering, linked_id) -> CourseOffering | None:
    """The offering this one goes with (a lab with its lecture): same term, never itself or a chain back to it."""
    if linked_id is None:
        return None
    found = CourseOffering.objects.filter(pk=linked_id, institution=institution).select_related("course").first()
    if found is None or found.term_id != offering.term_id:
        raise ValidationError({"linked_to": ["Choose an offering of the same term."]})
    node, seen = found, set()
    while node is not None and node.pk not in seen:
        if node.pk == offering.pk:
            raise ValidationError({"linked_to": ["An offering can't be linked back to itself."]})
        seen.add(node.pk)
        node = node.linked_to
    return found


def _lock_term(term_id) -> None:
    """Links are checked with the term's offerings locked, so A→B and B→A saved at once can't both pass."""
    list(CourseOffering.objects.select_for_update().filter(term_id=term_id).order_by("pk").values_list("pk", flat=True))


def save_offering(actor, institution, offering: CourseOffering | None, data: dict, version: int | None = None):
    with transaction.atomic():
        if offering is not None:
            if data.get("linked_to"):
                _lock_term(offering.term_id)  # before its own row, in one order, so two links can't deadlock
            offering = (
                CourseOffering.objects.select_for_update(of=("self",))
                .select_related("course", "term__year", "institution")
                .get(pk=offering.pk)
            )
            offering.check_version(version)
            _require(actor, offering)
            _open(offering.term)
            wanted = data.get("status", offering.status)
            if wanted != offering.status and (offering.status, wanted) not in FORWARD:
                raise Problem(409, "invalid_transition", f"A {offering.status} offering can't become {wanted}.")
            settled = offering.status in (CourseOffering.Status.CLOSED, CourseOffering.Status.CANCELLED)
            if settled and any(name in data for name in ("campus", "code", "capacity", "linked_to")):
                raise Problem(
                    409, "invalid_transition", f"{label(offering)} is {offering.status}; it no longer changes."
                )
        else:
            course = institution.courses.filter(pk=data["course"], is_active=True).first()
            if course is None:
                raise ValidationError({"course": ["Choose an active course."]})
            term = Term.objects.filter(pk=data["term"], year__institution=institution).select_related("year").first()
            if term is None:
                raise ValidationError({"term": ["Choose one of this institution's terms."]})
            offering = CourseOffering(institution=institution, course=course, term=term)
            if data.get("linked_to"):
                _lock_term(term.id)
        if "campus" in data:
            if (campus := institution.campuses.filter(pk=data["campus"], is_active=True).first()) is None:
                raise ValidationError({"campus": ["Choose an active campus."]})
            offering.campus = campus
        _require(actor, offering)
        _open(offering.term)
        for name in ("code", "capacity", "status"):
            if name in data:
                setattr(offering, name, data[name])
        if "linked_to" in data:
            offering.linked_to = _link(institution, offering, data["linked_to"])
        taken = CourseOffering.objects.filter(course=offering.course, term=offering.term, code=offering.code)
        if taken.exclude(pk=offering.pk).exists():
            raise ValidationError({"code": ["This course already has an offering with this code this term."]})
        offering.save()
        audit.log(actor, "offering.saved", offering, f"Offering {label(offering)} saved", institution=institution)
        return offering


def assign_teacher(actor, offering: CourseOffering, membership_id) -> TeachingAssignment:
    _require(actor, offering)
    _open(offering.term)
    if offering.status == CourseOffering.Status.CANCELLED:
        raise Problem(409, "cancelled", f"{label(offering)} is cancelled.")
    membership = _staff(offering.institution, membership_id, "membership")
    assignment = TeachingAssignment.objects.create(
        offering=offering, membership=membership, starts_on=today_for(offering.institution), created_by=actor
    )
    audit.log(
        actor,
        "offering.teacher_assigned",
        offering,
        f"{membership.user.full_name} teaches {label(offering)}",
        institution=offering.institution,
    )
    return assignment


def end_teaching(actor, offering: CourseOffering, assignment: TeachingAssignment) -> None:
    _require(actor, offering)
    today = today_for(offering.institution)
    if assignment.ends_on is not None and assignment.ends_on < today:
        raise Problem(409, "invalid_transition", "This assignment has already ended.")
    # As for sections: the last day it counted was yesterday.
    assignment.ends_on = today - dt.timedelta(days=1)
    assignment.save(update_fields=["ends_on"])
    audit.log(
        actor,
        "offering.teacher_ended",
        offering,
        f"{assignment.membership.user.full_name} no longer teaches {label(offering)}",
        institution=offering.institution,
    )


def offering_item(offering: CourseOffering, viewer) -> dict:
    today = today_for(offering.institution)
    course, term = offering.course, offering.term
    return {
        "id": str(offering.id),
        "version": offering.version,
        "label": label(offering),
        "code": offering.code,
        "capacity": offering.capacity,
        "registered": offering.registrations.filter(state="registered").count(),
        "pending": offering.registrations.filter(state="pending_approval").count(),
        "waitlisted": offering.registrations.filter(state="waitlisted").count(),
        "status": offering.status,
        "status_label": offering.get_status_display(),
        "course": {"id": str(course.id), "code": course.code, "title": course.title, "credits": str(course.credits)},
        "term": {"id": str(term.id), "name": term.name, "year": term.year.code, "year_status": term.year.status},
        "campus": {"id": str(offering.campus_id), "name": offering.campus.name},
        "linked_to": {"id": str(offering.linked_to_id), "label": label(offering.linked_to)}
        if offering.linked_to_id
        else None,
        "linked": [label(row) for row in offering.linked.select_related("course")],
        "teachers": [
            {
                "id": str(row.id),
                "membership": {"id": str(row.membership_id), "full_name": row.membership.user.full_name},
                "starts_on": row.starts_on,
                "ends_on": row.ends_on,
                "in_effect": in_effect(row, today),
            }
            for row in offering.teaching.select_related("membership__user")
        ],
        "can_manage": can_manage(viewer, offering),
    }
