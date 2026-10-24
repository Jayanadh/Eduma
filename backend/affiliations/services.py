"""Affiliation grants and result batches (slice 5e S5E-01..04). Every read and write rechecks the grant: approved, not
revoked and in its dates. The university only ever holds snapshots; the college's records stay the college's."""

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from academics.models import CourseAttempt, CurriculumVersion
from accounts.models import Membership, RoleAssignment
from accounts.permissions import WHOLE, has_perm, in_effect, today_for
from affiliations.models import AffiliationGrant, SubmissionBatch, SubmissionRow
from common import audit
from common.exceptions import Problem
from students.models import Enrollment

SUBMIT, REVIEW = "affiliation.submit", "affiliation.review"
COLLEGES = ("college", "engineering_college")


def grant_in_effect(grant: AffiliationGrant) -> bool:
    today = today_for(grant.college)
    return grant.status == AffiliationGrant.Status.ACTIVE and grant.starts_on <= today <= grant.ends_on


def _live(grant: AffiliationGrant) -> None:
    if not grant_in_effect(grant):
        raise Problem(409, "grant_inactive", "This affiliation grant is not in effect.")


def _is_admin(actor, institution) -> bool:
    rows = RoleAssignment.objects.filter(
        membership__user=actor,
        membership__institution=institution,
        membership__status=Membership.Status.ACTIVE,
        role_key="institution_admin",
    )
    return in_effect(rows, today_for(institution)).exists()


def propose(actor, data: dict) -> AffiliationGrant:
    college, university = data["college"], data["university"]
    if college.category not in COLLEGES:
        raise ValidationError({"college": ["Choose a college or an engineering college."]})
    if university.category != "university":
        raise ValidationError({"university": ["Choose a university."]})
    if data["ends_on"] < data["starts_on"]:
        raise ValidationError({"ends_on": ["End on or after the start."]})
    grant = AffiliationGrant.objects.create(proposed_by=actor, **data)
    audit.log(actor, "affiliation.proposed", grant, f"{college} → {university}: {grant.purpose}", institution=college)
    return grant


def approve(actor, grant: AffiliationGrant, version: int) -> AffiliationGrant:
    if not _is_admin(actor, grant.college):
        raise PermissionDenied("Only the college's Institution Admin approves its affiliation grants.")
    with transaction.atomic():
        grant = AffiliationGrant.objects.select_for_update().get(pk=grant.pk)
        grant.check_version(version)
        if grant.status != AffiliationGrant.Status.PROPOSED:
            raise Problem(409, "invalid_transition", "Only a proposed grant can be approved.")
        grant.status, grant.approved_by, grant.approved_at = AffiliationGrant.Status.ACTIVE, actor, timezone.now()
        grant.save()
        audit.log(
            actor,
            "affiliation.approved",
            grant,
            f"Affiliation with {grant.university} approved",
            institution=grant.college,
        )
        return grant


def revoke(actor, grant: AffiliationGrant, version: int, reason: str) -> AffiliationGrant:
    if not (_is_admin(actor, grant.college) or _is_admin(actor, grant.university)):
        raise PermissionDenied("Only either side's Institution Admin can revoke this grant.")
    with transaction.atomic():
        grant = AffiliationGrant.objects.select_for_update().get(pk=grant.pk)
        grant.check_version(version)
        if grant.status == AffiliationGrant.Status.REVOKED:
            return grant
        grant.status, grant.revoked_by, grant.revoked_at = AffiliationGrant.Status.REVOKED, actor, timezone.now()
        grant.revoked_reason = reason
        grant.save()
        for side in (grant.college, grant.university):
            audit.log(
                actor,
                "affiliation.revoked",
                grant,
                f"Affiliation {grant.college} → {grant.university} revoked: {reason}",
                institution=side,
            )
        return grant


def _term_label(term) -> str:
    return f"{term.year.code} {term.name}"


def _snapshot(enrollment: Enrollment, term) -> dict:
    student = enrollment.student
    attempts = list(CourseAttempt.objects.filter(enrollment=enrollment, term=term).select_related("course"))
    problems = []
    curriculum = enrollment.curriculum
    if curriculum is None:
        problems.append("No regulation is pinned.")
    elif curriculum.status == CurriculumVersion.Status.DRAFT:
        problems.append(f"{curriculum} is still a draft regulation.")
    problems += [
        f"{a.course.code} has no outcome yet." for a in attempts if a.outcome == CourseAttempt.Outcome.IN_PROGRESS
    ]
    if not attempts:
        problems.append("No courses this term.")
    return {
        "student": student,
        "number": student.number,
        "full_name": student.person.full_name,
        "program": enrollment.program.code if enrollment.program_id else "",
        "regulation": f"{enrollment.program.code} {curriculum}" if curriculum else "",
        "attempts": [
            {
                "course": a.course.code,
                "title": a.course.title,
                "credits": str(a.credits),
                "attempt_no": a.attempt_no,
                "outcome": a.outcome,
                "grade_point": str(a.grade_point) if a.grade_point is not None else None,
            }
            for a in attempts
        ],
        "problems": problems,
    }


def _require(actor, institution, perm: str) -> None:
    if not has_perm(actor, institution, perm, WHOLE):
        raise PermissionDenied("Your role does not cover affiliation batches.")


def build(actor, grant: AffiliationGrant, program, term) -> SubmissionBatch:
    _require(actor, grant.college, SUBMIT)
    _live(grant)
    enrollments = (
        Enrollment.objects.filter(institution=grant.college, program=program, attempts__term=term)
        .distinct()
        .select_related("student__person", "program", "curriculum")
    )
    with transaction.atomic():
        batch = SubmissionBatch.objects.create(
            grant=grant, program_code=program.code, term_label=_term_label(term), created_by=actor
        )
        for enrollment in enrollments:
            SubmissionRow.objects.create(batch=batch, **_snapshot(enrollment, term))
        audit.log(
            actor,
            "affiliation.batch_built",
            grant,
            f"Batch {program.code} {batch.term_label} drafted",
            institution=grant.college,
        )
        return batch


def _term_of(batch: SubmissionBatch):
    from academics.models import Term

    year, _, name = batch.term_label.partition(" ")
    return Term.objects.filter(year__institution=batch.grant.college, year__code=year, name=name).first()


def remove_row(actor, batch: SubmissionBatch, row: SubmissionRow) -> None:
    _require(actor, batch.grant.college, SUBMIT)
    if batch.status != SubmissionBatch.Status.DRAFT:
        raise Problem(409, "invalid_transition", "Only a draft batch changes.")
    row.delete()


def submit(actor, batch: SubmissionBatch) -> SubmissionBatch:
    _require(actor, batch.grant.college, SUBMIT)
    with transaction.atomic():
        batch = SubmissionBatch.objects.select_for_update().select_related("grant__college").get(pk=batch.pk)
        if batch.status != SubmissionBatch.Status.DRAFT:
            return batch  # a retry: the batch keeps its identity and nothing is sent twice
        _live(batch.grant)
        rows = list(batch.rows.all())
        if not rows:
            raise ValidationError({"rows": ["There is nothing to submit."]})
        if blocked := [r.number for r in rows if r.problems]:
            raise ValidationError({"rows": [f"Fix or remove these first: {', '.join(blocked)}."]})
        batch.status, batch.submitted_by, batch.submitted_at = SubmissionBatch.Status.SUBMITTED, actor, timezone.now()
        batch.save()
        audit.log(
            actor,
            "affiliation.batch_submitted",
            batch.grant,
            f"Batch {batch.program_code} {batch.term_label} revision {batch.revision} submitted ({len(rows)} students)",
            institution=batch.grant.college,
        )
        return batch


def revise(actor, batch: SubmissionBatch, corrections: list) -> SubmissionBatch:
    """The next revision: the rejected rows, re-read from the college's records, and any accepted rows chosen as
    corrections. Asking again returns the same draft."""
    _require(actor, batch.grant.college, SUBMIT)
    _live(batch.grant)
    with transaction.atomic():
        latest = (
            SubmissionBatch.objects.select_for_update().filter(reference=batch.reference).order_by("-revision").first()
        )
        if latest.status == SubmissionBatch.Status.DRAFT and latest.revision > 1:
            return latest
        if latest.pk != batch.pk or batch.status != SubmissionBatch.Status.REVIEWED:
            raise Problem(409, "invalid_transition", "Only the latest reviewed revision can be corrected.")
        term = _term_of(batch)
        chosen = {str(pk) for pk in corrections}
        rows = [
            r
            for r in batch.rows.select_related("student")
            if r.status == SubmissionRow.Status.REJECTED or str(r.id) in chosen
        ]
        if not rows:
            raise ValidationError({"corrections": ["Nothing was returned; choose accepted rows to correct."]})
        nxt = SubmissionBatch.objects.create(
            grant=batch.grant,
            reference=batch.reference,
            revision=batch.revision + 1,
            program_code=batch.program_code,
            term_label=batch.term_label,
            created_by=actor,
        )
        for row in rows:
            enrollment = row.student.enrollments.filter(status="active").first() or row.student.enrollments.first()
            SubmissionRow.objects.create(
                batch=nxt, is_correction=row.status == SubmissionRow.Status.ACCEPTED, **_snapshot(enrollment, term)
            )
        return nxt


def received(university):
    """Batches the university may see now: submitted or reviewed, under grants in effect today."""
    today = today_for(university)
    return SubmissionBatch.objects.filter(
        grant__university=university,
        grant__status=AffiliationGrant.Status.ACTIVE,
        grant__starts_on__lte=today,
        grant__ends_on__gte=today,
        status__in=(SubmissionBatch.Status.SUBMITTED, SubmissionBatch.Status.REVIEWED),
    ).select_related("grant__college", "grant__university")


def decide(actor, batch: SubmissionBatch, row: SubmissionRow, decision: str, reason: str) -> SubmissionBatch:
    _require(actor, batch.grant.university, REVIEW)
    if decision == SubmissionRow.Status.REJECTED and not reason.strip():
        raise ValidationError({"reason": ["Say what needs correcting."]})
    with transaction.atomic():
        batch = SubmissionBatch.objects.select_for_update().select_related("grant").get(pk=batch.pk)
        _live(batch.grant)
        row = SubmissionRow.objects.select_for_update().get(pk=row.pk)
        if row.status != SubmissionRow.Status.PENDING:
            raise Problem(409, "invalid_transition", "This row has already been decided.")
        row.status, row.reason = decision, reason.strip()
        row.decided_by, row.decided_at = actor, timezone.now()
        row.save()
        if not batch.rows.filter(status=SubmissionRow.Status.PENDING).exists():
            batch.status = SubmissionBatch.Status.REVIEWED
            batch.save(update_fields=["status"])
        audit.log(
            actor,
            "affiliation.row_decided",
            batch.grant,
            f"{row.number} in {batch.program_code} {batch.term_label} r{batch.revision}: {decision}",
            institution=batch.grant.university,
        )
        return batch


def grant_item(grant: AffiliationGrant) -> dict:
    return {
        "id": str(grant.id),
        "version": grant.version,
        "college": {"id": str(grant.college_id), "name": grant.college.display_name},
        "university": {"id": str(grant.university_id), "name": grant.university.display_name},
        "purpose": grant.purpose,
        "categories": list(AffiliationGrant.CATEGORIES),
        "actions": list(AffiliationGrant.ACTIONS),
        "starts_on": grant.starts_on,
        "ends_on": grant.ends_on,
        "evidence": grant.evidence,
        "status": grant.status,
        "status_label": grant.get_status_display(),
        "in_effect": grant_in_effect(grant),
        "revoked_reason": grant.revoked_reason,
    }


def _current(batch: SubmissionBatch) -> dict:
    """{number: id of that student's latest accepted row} for the grant: the university's current record."""
    rows = SubmissionRow.objects.filter(batch__grant=batch.grant, batch__reference=batch.reference, status="accepted")
    latest = rows.values("number").annotate(top=Max("batch__revision"))
    tops = {r["number"]: r["top"] for r in latest}
    return {r.number: r.id for r in rows.select_related("batch") if r.batch.revision == tops[r.number]}


def batch_item(batch: SubmissionBatch, for_university: bool = False) -> dict:
    current = _current(batch)
    return {
        "id": str(batch.id),
        "reference": str(batch.reference),
        "revision": batch.revision,
        "program": batch.program_code,
        "term": batch.term_label,
        "status": batch.status,
        "status_label": batch.get_status_display(),
        "college": batch.grant.college.display_name,
        "university": batch.grant.university.display_name,
        "grant": str(batch.grant_id),
        "submitted_at": batch.submitted_at,
        "rows": [
            {
                "id": str(row.id),
                "number": row.number,
                "full_name": row.full_name,
                "program": row.program,
                "regulation": row.regulation,
                "attempts": row.attempts,
                "problems": row.problems,
                "is_correction": row.is_correction,
                "status": row.status,
                "status_label": row.get_status_display(),
                "reason": row.reason,
                "current": current.get(row.number) == row.id,
            }
            for row in batch.rows.all()
        ],
    }


def found_or_404(queryset, pk):
    row = queryset.filter(pk=pk).first()
    if row is None:
        raise NotFound()
    return row
