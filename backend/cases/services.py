"""Service cases (slice 10c S10C-01..04). What anyone sees is decided per case by `access`: the requester, the current
assignee, or triage (only the shell of a confidential case). Everyone else gets nothing, not even that it exists."""

import datetime as dt

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import Membership
from accounts.permissions import has_perm
from cases.models import Appeal, CaseAssignment, CaseNote, Resolution, ServiceCase
from common import audit
from common.exceptions import Problem
from communication.services import notify
from institutions.models import Institution

ASSIGN, CONFIDENTIAL = "service_case.assign", "service_case.confidential"
Type, State, Visibility = ServiceCase.Type, ServiceCase.State, CaseNote.Visibility
RESPONSE_DAYS = {Type.SERVICE: 7, Type.GRIEVANCE: 15, Type.COUNSELLING: 3, Type.SAFEGUARDING: 1}
APPEAL_DAYS = 15


def access(user, institution, case: ServiceCase) -> str | None:
    """'officer' (the current assignee), 'requester', 'triage', or None."""
    if case.assignee_id and case.assignee.user_id == user.id:
        return "officer"
    if case.requester_id == user.id:
        return "requester"
    if has_perm(user, institution, ASSIGN):
        return "triage"
    return None


def visible(user, institution, search: str = ""):
    rows = ServiceCase.objects.filter(institution=institution).select_related("assignee__user", "requester")
    mine = Q(requester=user) | Q(assignee__user=user)
    if not has_perm(user, institution, ASSIGN):
        rows = rows.filter(mine)
    if len(search) >= 3:  # confidential subjects are searchable only by the requester and the assignee
        rows = rows.filter(Q(subject__icontains=search) | Q(number__iexact=search)).filter(Q(confidential=False) | mine)
    return rows


def find(user, institution, pk) -> tuple[ServiceCase, str]:
    case = ServiceCase.objects.filter(institution=institution, pk=pk).select_related("assignee__user").first()
    seen = case and access(user, institution, case)
    if not seen:
        raise NotFound()
    return case, seen


def open_case(actor, institution, case_type: str, subject: str, description: str) -> ServiceCase:
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=institution.pk)  # numbers in order, never twice
        count = ServiceCase.objects.filter(institution=institution).count()
        case = ServiceCase.objects.create(
            institution=institution,
            number=f"SC-{count + 1:04d}",
            case_type=case_type,
            confidential=case_type != Type.SERVICE,
            subject=subject,
            description=description,
            requester=actor,
            due_at=timezone.now() + dt.timedelta(days=RESPONSE_DAYS[case_type]),
        )
    audit.log(actor, "service_case.opened", case, f"Opened {case.number}")  # no subject: it may be confidential
    return case


def _locked(case: ServiceCase, *allowed) -> ServiceCase:
    case = ServiceCase.objects.select_for_update().get(pk=case.pk)
    if case.state not in allowed:
        raise Problem(409, "invalid_transition", f"This case is {case.get_state_display().lower()}.")
    return case


def assign(actor, institution, case: ServiceCase, assignee: Membership) -> ServiceCase:
    if not has_perm(actor, institution, ASSIGN):
        raise PermissionDenied("Only triage assigns cases.")
    if assignee.kind != Membership.Kind.STAFF or assignee.status != Membership.Status.ACTIVE:
        raise ValidationError({"assignee": ["Assign an active staff member."]})
    if assignee.user_id == case.requester_id:
        raise ValidationError({"assignee": ["Nobody handles their own case."]})
    if case.confidential and not has_perm(assignee.user, institution, CONFIDENTIAL):
        raise ValidationError({"assignee": ["Confidential cases go only to officers allowed to handle them."]})
    with transaction.atomic():
        case = _locked(case, State.SUBMITTED, State.ASSIGNED, State.APPEALED)
        first = case.resolutions.first()
        if Appeal.objects.filter(case=case).exists() and first and first.by_id == assignee.user_id:
            raise ValidationError({"assignee": ["Someone other than the first resolver reviews the appeal."]})
        case.assignee, case.state = assignee, State.ASSIGNED
        case.save(update_fields=["assignee", "state"])
        CaseAssignment.objects.create(case=case, assignee=assignee, by=actor)
    notify(assignee.user, institution, f"{case.number} was assigned to you.", f"/app/cases/{case.id}")
    audit.log(actor, "service_case.assigned", case, f"Assigned {case.number} to {assignee.user.full_name}")
    return case


def _requester_link(case: ServiceCase) -> str:
    """Staff open their own cases in the workspace; students and guardians in their portal."""
    staff = Membership.objects.filter(
        institution_id=case.institution_id, user_id=case.requester_id, kind=Membership.Kind.STAFF
    ).exists()
    return f"/app/cases/{case.id}" if staff else f"/cases/{case.id}"


def add_note(actor, institution, case: ServiceCase, text: str, internal: bool) -> CaseNote:
    seen = access(actor, institution, case)
    if seen not in ("officer", "requester") or (internal and seen != "officer"):
        raise PermissionDenied("Only the requester and the officer on the case write on it.")
    if not text.strip():
        raise ValidationError({"text": ["Write something."]})
    note = CaseNote.objects.create(
        case=case, author=actor, text=text.strip(), visibility=Visibility.INTERNAL if internal else Visibility.REQUESTER
    )
    if seen == "officer" and not internal:
        notify(case.requester, institution, f"There's an update on {case.number}.", _requester_link(case))
    elif seen == "requester" and case.assignee_id:
        notify(case.assignee.user, institution, f"The requester replied on {case.number}.", f"/app/cases/{case.id}")
    return note


def resolve(actor, institution, case: ServiceCase, text: str) -> ServiceCase:
    if access(actor, institution, case) != "officer":
        raise PermissionDenied("The officer on the case resolves it.")
    if not text.strip():
        raise ValidationError({"text": ["Say how it was resolved."]})
    with transaction.atomic():
        case = _locked(case, State.ASSIGNED)
        stage = "appeal" if Appeal.objects.filter(case=case).exists() else "original"
        Resolution.objects.create(case=case, stage=stage, text=text.strip(), by=actor)
        case.state = State.RESOLVED
        case.save(update_fields=["state"])
    notify(case.requester, institution, f"{case.number} is resolved.", _requester_link(case))
    audit.log(actor, "service_case.resolved", case, f"Resolved {case.number} ({stage})")
    return case


def appeal(actor, institution, case: ServiceCase, reason: str) -> ServiceCase:
    """Once, within 15 days; back to triage, with the first resolution kept."""
    if case.requester_id != actor.id:
        raise PermissionDenied("Only the requester appeals.")
    if not reason.strip():
        raise ValidationError({"reason": ["Say why you are appealing."]})
    with transaction.atomic():
        case = _locked(case, State.RESOLVED)
        if Appeal.objects.filter(case=case).exists():
            raise Problem(409, "appeal_used", "This case has already been appealed once.")
        if case.resolutions.last().at < timezone.now() - dt.timedelta(days=APPEAL_DAYS):
            raise Problem(409, "appeal_closed", f"Appeals are open for {APPEAL_DAYS} days after the resolution.")
        Appeal.objects.create(case=case, reason=reason.strip())
        case.state, case.assignee = State.APPEALED, None
        case.save(update_fields=["state", "assignee"])
    audit.log(actor, "service_case.appealed", case, f"Appealed {case.number}")
    return case


def officers(institution, confidential: bool) -> list[dict]:
    """Staff a case can be assigned to: for a confidential case, only those allowed to handle one."""
    people = Membership.objects.filter(
        institution=institution, kind=Membership.Kind.STAFF, status=Membership.Status.ACTIVE
    ).select_related("user")
    # shortcut: checks each member's grants in Python; fine to a few hundred staff, then a permission index query
    return [
        {"id": str(m.id), "name": m.user.full_name}
        for m in people.order_by("user__full_name")[:500]
        if not confidential or has_perm(m.user, institution, CONFIDENTIAL)
    ]


def item(case: ServiceCase, seen: str, detail=False) -> dict:
    """The projection for who is looking (S10C-02): fields are added, never filtered after the fact."""
    shell = {
        "id": str(case.id),
        "number": case.number,
        "case_type": case.case_type,
        "type_label": case.get_case_type_display(),
        "confidential": case.confidential,
        "state": case.state,
        "state_label": case.get_state_display(),
        "created_at": case.created_at.isoformat(),
        "seen_as": seen,
    }
    if seen in ("officer", "triage"):
        shell |= {
            "due_at": case.due_at.isoformat(),
            "overdue": case.state != State.RESOLVED and case.due_at < timezone.now(),
            "assignee": case.assignee.user.full_name if case.assignee_id else None,
        }
    if seen == "triage" and case.confidential:
        return shell
    shell |= {"subject": case.subject, "description": case.description}
    if seen == "officer":
        shell["requester"] = case.requester.full_name
    if not detail or seen == "triage":
        return shell
    notes = case.notes.select_related("author")
    if seen == "requester":
        notes = notes.filter(visibility=Visibility.REQUESTER)
    appealed = Appeal.objects.filter(case=case).first()
    last = case.resolutions.last()
    shell |= {
        "notes": [
            {"text": n.text, "visibility": n.visibility, "by": n.author.full_name, "at": n.at.isoformat()}
            for n in notes
        ],
        "resolutions": [{"stage": r.stage, "text": r.text, "at": r.at.isoformat()} for r in case.resolutions.all()],
        "appeal": {"reason": appealed.reason, "at": appealed.at.isoformat()} if appealed else None,
        "can_appeal": seen == "requester"
        and case.state == State.RESOLVED
        and appealed is None
        and last.at >= timezone.now() - dt.timedelta(days=APPEAL_DAYS),
    }
    return shell
