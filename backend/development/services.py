"""Placements, internships, alumni, research and quality evidence (slice 10c S10C-05..09)."""

import hashlib
import json
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.progress import progress
from accounts.models import Membership
from accounts.permissions import has_perm, today_for
from admissions.documents import MAX_BYTES, sniff
from common import audit
from common.exceptions import Problem
from development.models import (
    AlumniProfile,
    EvidenceRequest,
    EvidenceVersion,
    Internship,
    Milestone,
    Opportunity,
    PlacementApplication,
    ReviewCycle,
    Scholar,
    Supervision,
)

PLACEMENT, RESEARCH, QUALITY = "placement.manage", "research.manage", "quality_evidence.manage"
Applied = PlacementApplication.State
# Who moves an application where: the placement office up to an offer; the student decides the offer.
OFFICE_MOVES = {
    Applied.SHORTLISTED: (Applied.APPLIED,),
    Applied.OFFERED: (Applied.APPLIED, Applied.SHORTLISTED),
    Applied.REJECTED: (Applied.APPLIED, Applied.SHORTLISTED),
}


def require(actor, institution, perm: str, message: str) -> None:
    if not has_perm(actor, institution, perm):
        raise PermissionDenied(message)


def staff_member(institution, username: str) -> Membership:
    found = Membership.objects.filter(
        institution=institution,
        kind=Membership.Kind.STAFF,
        status=Membership.Status.ACTIVE,
        user__username=str(username or "").strip().lower(),
    ).first()
    if found is None:
        raise ValidationError({"username": ["No active staff member has that username."]})
    return found


# Placements (S10C-05)


def eligibility(student, opportunity: Opportunity) -> dict:
    """What decides whether a student may apply, as it stands now; kept on the application as it was."""
    today = today_for(opportunity.institution)
    enrollment = student.enrollments.filter(status="active").select_related("curriculum", "program").first()
    programs = list(opportunity.programs.values_list("id", flat=True))
    cgpa = progress(enrollment)["cgpa"] if enrollment and enrollment.curriculum_id else None
    reasons = []
    if opportunity.closes_on < today:
        reasons.append("Applications have closed.")
    if programs and (enrollment is None or enrollment.program_id not in programs):
        reasons.append("Not open to your program.")
    if opportunity.min_cgpa is not None and (cgpa is None or Decimal(cgpa) < opportunity.min_cgpa):
        reasons.append(f"Needs a CGPA of {opportunity.min_cgpa}.")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "program": enrollment.program.code if enrollment and enrollment.program_id else None,
        "cgpa": cgpa,
        "checked_on": today.isoformat(),
    }


def apply(student, opportunity: Opportunity, consent: bool) -> PlacementApplication:
    if not consent:
        raise ValidationError({"consent": ["Agree to share your profile with this employer to apply."]})
    checked = eligibility(student, opportunity)
    if not checked["eligible"]:
        raise ValidationError({"opportunity": checked["reasons"]})
    try:
        with transaction.atomic():
            made = PlacementApplication.objects.create(
                opportunity=opportunity, student=student, consented_at=timezone.now(), eligibility=checked
            )
    except IntegrityError:
        raise Problem(409, "already_applied", "You have already applied for this.") from None
    audit.log(
        student.user, "placement.applied", made, f"Applied for {opportunity.title}", institution=student.institution
    )
    return made


def _move(application, allowed, to) -> PlacementApplication:
    with transaction.atomic():
        application = PlacementApplication.objects.select_for_update().get(pk=application.pk)
        if application.state not in allowed:
            raise Problem(409, "invalid_transition", f"This application is {application.get_state_display().lower()}.")
        application.state = to
        application.save(update_fields=["state"])
        if to == Applied.ACCEPTED and application.opportunity.kind == Opportunity.Kind.INTERNSHIP:
            Internship.objects.create(application=application)
    return application


def office_move(actor, institution, application, to: str) -> PlacementApplication:
    require(actor, institution, PLACEMENT, "Only the placement office moves applications.")
    if to not in OFFICE_MOVES:
        raise ValidationError({"state": ["Shortlist, offer or decline."]})
    done = _move(application, OFFICE_MOVES[to], to)
    audit.log(actor, f"placement.{to}", done, f"{done.get_state_display()}: {done.student.person.full_name}")
    return done


def student_decides(application, accept: bool | None) -> PlacementApplication:
    """accept True/False decides an offer; None withdraws an open application."""
    if accept is None:
        return _move(application, (Applied.APPLIED, Applied.SHORTLISTED, Applied.OFFERED), Applied.WITHDRAWN)
    return _move(application, (Applied.OFFERED,), Applied.ACCEPTED if accept else Applied.DECLINED)


def report(institution) -> list[dict]:
    """Offers and accepted placements counted apart (WF-OPS: an offer is not a placement)."""
    rows = (
        Opportunity.objects.filter(institution=institution)
        .select_related("employer")
        .annotate(
            applied=Count("applications"),
            offered=Count(
                "applications", filter=Q(applications__state__in=[Applied.OFFERED, Applied.ACCEPTED, Applied.DECLINED])
            ),
            accepted=Count("applications", filter=Q(applications__state=Applied.ACCEPTED)),
        )
    )
    return [
        {
            "opportunity": o.title,
            "employer": o.employer.name,
            "kind": o.kind,
            "applied": o.applied,
            "offers": o.offered,
            "accepted": o.accepted,
        }
        for o in rows
    ]


def application_item(a: PlacementApplication, office=False) -> dict:
    item = {
        "id": str(a.id),
        "opportunity": {
            "id": str(a.opportunity_id),
            "title": a.opportunity.title,
            "employer": a.opportunity.employer.name,
            "kind": a.opportunity.kind,
        },
        "state": a.state,
        "created_at": a.created_at.isoformat(),
    }
    if office:
        item |= {
            "student": {"number": a.student.number, "name": a.student.person.full_name},
            "eligibility": a.eligibility,
        }
    return item


def opportunity_item(o: Opportunity) -> dict:
    return {
        "id": str(o.id),
        "title": o.title,
        "kind": o.kind,
        "employer": o.employer.name,
        "description": o.description,
        "programs": [p.code for p in o.programs.all()],
        "min_cgpa": str(o.min_cgpa) if o.min_cgpa is not None else None,
        "closes_on": o.closes_on.isoformat(),
    }


# Internships (S10C-06)


def set_supervisor(actor, institution, internship: Internship, supervisor: Membership) -> Internship:
    require(actor, institution, PLACEMENT, "Only the placement office assigns supervisors.")
    internship.supervisor = supervisor
    internship.save(update_fields=["supervisor"])
    return internship


def evaluate(actor, institution, internship: Internship, score, remarks: str) -> Internship:
    mine = internship.supervisor_id and internship.supervisor.user_id == actor.id
    if not (mine or has_perm(actor, institution, PLACEMENT)):
        raise PermissionDenied("Only the supervisor evaluates the internship.")
    internship.score, internship.remarks = score, remarks
    internship.evaluated_by, internship.evaluated_at = actor, timezone.now()
    internship.save()
    audit.log(actor, "internship.evaluated", internship, "Internship evaluated", institution=institution)
    return internship


def internship_item(i: Internship) -> dict:
    a = i.application
    return {
        "id": str(i.id),
        "student": {"number": a.student.number, "name": a.student.person.full_name},
        "opportunity": a.opportunity.title,
        "employer": a.opportunity.employer.name,
        "supervisor": i.supervisor.user.full_name if i.supervisor_id else None,
        "score": str(i.score) if i.score is not None else None,
        "remarks": i.remarks,
        "evaluated_at": i.evaluated_at.isoformat() if i.evaluated_at else None,
    }


# Alumni (S10C-07)


def save_alumni(student, data: dict) -> AlumniProfile:
    if not data.get("consent"):
        raise ValidationError({"consent": ["Agree to be listed to keep a profile."]})
    profile, _ = AlumniProfile.objects.get_or_create(student=student)
    for key in ("email", "phone", "occupation"):
        setattr(profile, key, data.get(key, ""))
    profile.consented_at, profile.withdrawn_at = timezone.now(), None
    profile.save()
    return profile


def withdraw_alumni(student) -> None:
    AlumniProfile.objects.filter(student=student).update(withdrawn_at=timezone.now(), email="", phone="", occupation="")


def alumni_item(p: AlumniProfile) -> dict:
    return {
        "student": {"number": p.student.number, "name": p.student.person.full_name},
        "email": p.email,
        "phone": p.phone,
        "occupation": p.occupation,
        "consented_at": p.consented_at.isoformat() if p.consented_at else None,
        "listed": p.consented_at is not None and p.withdrawn_at is None,
    }


# Research (S10C-08)


def supervising(user, institution):
    today = today_for(institution)
    return Supervision.objects.filter(supervisor__user=user, starts_on__lte=today).filter(
        Q(ends_on__isnull=True) | Q(ends_on__gt=today)  # an ended supervision ends that day
    )


def scholars_for(user, institution):
    rows = Scholar.objects.filter(institution=institution).select_related("student__person")
    if has_perm(user, institution, RESEARCH):
        return rows
    return rows.filter(id__in=supervising(user, institution).values("scholar_id"))


def submit_milestone(scholar: Scholar, milestone: Milestone, summary: str) -> Milestone:
    today = today_for(scholar.institution)
    if milestone.needs_ethics and not scholar.ethics.filter(valid_from__lte=today, valid_to__gte=today).exists():
        raise Problem(409, "ethics_required", "This milestone needs an ethics approval valid today.")
    with transaction.atomic():
        milestone = Milestone.objects.select_for_update().get(pk=milestone.pk)
        if milestone.state not in (Milestone.State.PENDING, Milestone.State.RETURNED):
            raise Problem(409, "invalid_transition", f"This milestone is {milestone.get_state_display().lower()}.")
        milestone.state, milestone.summary = Milestone.State.SUBMITTED, summary
        milestone.save(update_fields=["state", "summary"])
    return milestone


def decide_milestone(actor, institution, milestone: Milestone, approve: bool, note: str) -> Milestone:
    """A current supervisor decides; the scholar never approves their own work."""
    if not supervising(actor, institution).filter(scholar=milestone.scholar).exists():
        raise PermissionDenied("Only a current supervisor approves milestones.")
    with transaction.atomic():
        milestone = Milestone.objects.select_for_update().get(pk=milestone.pk)
        if milestone.state != Milestone.State.SUBMITTED:
            raise Problem(409, "invalid_transition", "Only a submitted milestone is decided.")
        milestone.state = Milestone.State.APPROVED if approve else Milestone.State.RETURNED
        milestone.note, milestone.decided_by = note, actor
        milestone.save(update_fields=["state", "note", "decided_by"])
    audit.log(actor, f"milestone.{milestone.state}", milestone, milestone.title, institution=institution)
    return milestone


def scholar_item(s: Scholar) -> dict:
    today = today_for(s.institution)
    return {
        "id": str(s.id),
        "student": {"number": s.student.number, "name": s.student.person.full_name},
        "topic": s.topic,
        "started_on": s.started_on.isoformat(),
        "supervisors": [
            {
                "id": str(x.id),
                "name": x.supervisor.user.full_name,
                "role": x.role,
                "current": x.ends_on is None or x.ends_on > today,
            }
            for x in s.supervisions.select_related("supervisor__user")
        ],
        "ethics": [
            {
                "reference": e.reference,
                "committee": e.committee,
                "valid_from": e.valid_from.isoformat(),
                "valid_to": e.valid_to.isoformat(),
                "valid": e.valid_from <= today <= e.valid_to,
            }
            for e in s.ethics.all()
        ],
        "milestones": [
            {
                "id": str(m.id),
                "title": m.title,
                "due_on": m.due_on.isoformat(),
                "needs_ethics": m.needs_ethics,
                "state": m.state,
                "summary": m.summary,
                "note": m.note,
            }
            for m in s.milestones.all()
        ],
    }


# Quality evidence (S10C-09)


def upload(actor, request: EvidenceRequest, file) -> EvidenceVersion:
    """A version is kept only once the file is checked and stored: a failed upload changes nothing."""
    if request.owner.user_id != actor.id:
        raise PermissionDenied("Only the evidence owner uploads it.")
    if request.cycle.frozen_at:
        raise Problem(409, "cycle_frozen", "This review cycle is frozen.")
    if file is None:
        raise ValidationError({"file": ["Choose a file."]})
    if file.size > MAX_BYTES:
        raise ValidationError({"file": ["Files can be up to 5 MB."]})
    content_type, extension = sniff(file)
    digest = hashlib.sha256()
    for chunk in file.chunks():
        digest.update(chunk)
    file.seek(0)
    with transaction.atomic():
        request = EvidenceRequest.objects.select_for_update().get(pk=request.pk)
        if request.state == EvidenceRequest.State.ACCEPTED:
            raise Problem(409, "invalid_transition", "This evidence is already accepted.")
        number = request.versions.count() + 1
        version = EvidenceVersion(
            request=request,
            number=number,
            original_name=file.name[:200],
            content_type=content_type,
            sha256=digest.hexdigest(),
            uploaded_by=actor,
        )
        version.file.save(f"v{number}.{extension}", file, save=False)
        version.save()
        request.state = EvidenceRequest.State.SUBMITTED
        request.save(update_fields=["state"])
    return version


def review(actor, institution, request: EvidenceRequest, accept: bool, note: str) -> EvidenceRequest:
    require(actor, institution, QUALITY, "Only the quality office reviews evidence.")
    if request.owner.user_id == actor.id:
        raise PermissionDenied("Someone other than the owner reviews evidence.")
    with transaction.atomic():
        request = EvidenceRequest.objects.select_for_update().select_related("cycle").get(pk=request.pk)
        if request.cycle.frozen_at or request.state != EvidenceRequest.State.SUBMITTED:
            raise Problem(409, "invalid_transition", "Only submitted evidence in an open cycle is reviewed.")
        request.state = EvidenceRequest.State.ACCEPTED if accept else EvidenceRequest.State.RETURNED
        request.note = note
        request.save(update_fields=["state", "note"])
    return request


def freeze(actor, institution, cycle: ReviewCycle) -> ReviewCycle:
    require(actor, institution, QUALITY, "Only the quality office freezes a cycle.")
    with transaction.atomic():
        cycle = ReviewCycle.objects.select_for_update().get(pk=cycle.pk)
        if cycle.frozen_at:
            raise Problem(409, "cycle_frozen", "This review cycle is already frozen.")
        requests = list(cycle.requests.select_related("owner__user").prefetch_related("versions"))
        missing = [f"{r.criterion} {r.title}" for r in requests if r.state != EvidenceRequest.State.ACCEPTED]
        if not requests or missing:
            raise ValidationError(
                {"requests": [f"Not accepted yet: {', '.join(missing)}." if missing else "Nothing requested."]}
            )
        snapshot = {
            "framework": cycle.framework,
            "period": cycle.period,
            "evidence": [
                {
                    "criterion": r.criterion,
                    "title": r.title,
                    "owner": r.owner.user.full_name,
                    "version": r.versions.last().number,
                    "sha256": r.versions.last().sha256,
                }
                for r in requests
            ],
            "note": "Evidence assembled by the institution; not an accreditation decision.",
        }
        cycle.snapshot = snapshot
        cycle.snapshot_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        cycle.frozen_at = timezone.now()
        cycle.save()
    audit.log(actor, "review_cycle.frozen", cycle, f"Froze {cycle.framework} {cycle.period}", institution=institution)
    return cycle


def request_item(r: EvidenceRequest) -> dict:
    return {
        "id": str(r.id),
        "cycle": {"id": str(r.cycle_id), "framework": r.cycle.framework, "period": r.cycle.period},
        "criterion": r.criterion,
        "title": r.title,
        "owner": r.owner.user.full_name,
        "state": r.state,
        "note": r.note,
        "versions": [
            {
                "id": str(v.id),
                "number": v.number,
                "name": v.original_name,
                "sha256": v.sha256,
                "uploaded_at": v.uploaded_at.isoformat(),
            }
            for v in r.versions.all()
        ],
    }


def cycle_item(c: ReviewCycle, requests=False) -> dict:
    item = {
        "id": str(c.id),
        "framework": c.framework,
        "period": c.period,
        "frozen_at": c.frozen_at.isoformat() if c.frozen_at else None,
        "snapshot_hash": c.snapshot_hash,
    }
    if requests:
        item["requests"] = [request_item(r) for r in c.requests.select_related("owner__user", "cycle")]
    return item
