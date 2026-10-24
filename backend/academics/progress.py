"""Attempts, grade-point averages, transfer credit and advisory degree progress (slice 5d S5D-01..05, EX-03).

Averages are worked out exactly from the attempts every time and only rounded for display; a repeat adds an attempt and
the regulation's repeat rule decides which attempts count, while credits count once per course."""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.models import CourseAttempt, CourseRegistration, CreditTransfer, CurriculumVersion
from accounts.permissions import has_perm
from common import audit
from common.exceptions import Problem
from students.models import Enrollment, Student

RECORD = "academic_record.manage"
Outcome = CourseAttempt.Outcome
GRADED = (Outcome.PASSED, Outcome.FAILED)
ZERO = Decimal(0)


def _require(actor, student: Student) -> None:
    if not has_perm(actor, student.institution, RECORD, student.scope):
        raise PermissionDenied("Your role does not cover this student's academic record.")


def record_outcome(actor, attempt: CourseAttempt, data: dict) -> CourseAttempt:
    student = attempt.enrollment.student
    _require(actor, student)
    outcome, grade_point = data["outcome"], data.get("grade_point")
    if outcome in GRADED and grade_point is None:
        raise ValidationError({"grade_point": ["A pass or a fail needs its grade point."]})
    if outcome not in GRADED and grade_point is not None:
        raise ValidationError({"grade_point": ["Only a pass or a fail has a grade point."]})
    with transaction.atomic():
        attempt = CourseAttempt.objects.select_for_update().get(pk=attempt.pk)
        if attempt.outcome == Outcome.WITHDRAWN:
            raise Problem(409, "invalid_transition", "A withdrawn attempt keeps its outcome.")
        before = attempt.outcome
        attempt.outcome, attempt.grade_point = outcome, grade_point
        attempt.recorded_by, attempt.recorded_at = actor, timezone.now()
        attempt.save()
        audit.log(
            actor,
            "attempt.outcome_recorded",
            student,
            f"{student.number} {attempt.course.code} attempt {attempt.attempt_no}: {attempt.get_outcome_display()}",
            institution=student.institution,
            changes={
                "outcome": {"from": before, "to": outcome},
                "grade_point": str(grade_point) if grade_point else None,
            },
        )
        return attempt


def add_transfer(actor, student: Student, enrollment: Enrollment, data: dict) -> CreditTransfer:
    _require(actor, student)
    transfer = CreditTransfer.objects.create(
        institution=student.institution, enrollment=enrollment, created_by=actor, **data
    )
    audit.log(
        actor,
        "transfer.recorded",
        student,
        f"{student.number}: {transfer.source_course} from {transfer.source_institution}",
        institution=student.institution,
    )
    return transfer


def decide_transfer(actor, transfer: CreditTransfer, data: dict) -> CreditTransfer:
    student = transfer.enrollment.student
    _require(actor, student)
    with transaction.atomic():
        transfer = CreditTransfer.objects.select_for_update().get(pk=transfer.pk)
        transfer.check_version(data["version"])
        if transfer.decision != CreditTransfer.Decision.PENDING:
            raise Problem(409, "invalid_transition", "This transfer has already been decided.")
        if data["decision"] == CreditTransfer.Decision.APPROVED:
            for name in ("approved_credits", "awarding_authority"):
                if not data.get(name):
                    raise ValidationError({name: ["An approval needs this."]})
            if data.get("course") and not student.institution.courses.filter(pk=data["course"]).exists():
                raise ValidationError({"course": ["Choose one of this institution's courses."]})
            transfer.approved_credits = data["approved_credits"]
            transfer.awarding_authority = data["awarding_authority"]
            transfer.course_id = data.get("course")
            transfer.category = data.get("category", "")
        transfer.decision = data["decision"]
        transfer.decided_by, transfer.decided_at = actor, timezone.now()
        transfer.save()
        audit.log(
            actor,
            "transfer.decided",
            student,
            f"{student.number}: {transfer.source_course} {transfer.get_decision_display().lower()}",
            institution=student.institution,
        )
        return transfer


def counted(attempts: list, rule: str) -> list:
    """The graded attempts that count in an average under the regulation's repeat rule (S5D-02)."""
    graded = [a for a in attempts if a.outcome in GRADED and a.grade_point is not None]
    if rule == CurriculumVersion.RepeatRule.ALL:
        return graded
    chosen: dict = {}
    for item in sorted(graded, key=lambda a: a.attempt_no):
        current = chosen.get(item.course_id)
        if rule == CurriculumVersion.RepeatRule.REPLACE or current is None or item.grade_point > current.grade_point:
            chosen[item.course_id] = item
    return list(chosen.values())


def average(attempts: list) -> Decimal | None:
    credits = sum((a.credits for a in attempts), ZERO)
    return sum((a.credits * a.grade_point for a in attempts), ZERO) / credits if credits else None


def shown(value: Decimal | None) -> str | None:
    """Two decimals, half up — for display only; nothing is averaged from rounded figures (EX-03)."""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if value is not None else None


def _credits(value) -> str:
    return str(Decimal(value).quantize(Decimal("0.1")))


def progress(enrollment: Enrollment) -> dict:
    """Advisory degree progress against the pinned regulation (S5D-05). Never an award."""
    curriculum = enrollment.curriculum
    rule = curriculum.repeat_rule if curriculum else CurriculumVersion.RepeatRule.REPLACE
    attempts = list(
        enrollment.attempts.select_related("course", "term__year").order_by("term__starts_on", "attempt_no")
    )
    transfers = list(enrollment.transfers.filter(decision=CreditTransfer.Decision.APPROVED).select_related("course"))
    passed = {a.course_id: a.credits for a in attempts if a.outcome == Outcome.PASSED}
    credited = {t.course_id: t.approved_credits for t in transfers if t.course_id and t.course_id not in passed}
    going = {a.course_id for a in attempts if a.outcome == Outcome.IN_PROGRESS}
    going |= set(
        enrollment.registrations.filter(state=CourseRegistration.State.PENDING).values_list(
            "offering__course_id", flat=True
        )
    )
    earned = sum(passed.values(), ZERO) + sum(
        (t.approved_credits for t in transfers if t.course_id not in passed), ZERO
    )
    entries = list(curriculum.courses.select_related("course").prefetch_related("prerequisites")) if curriculum else []
    in_regulation = {e.course_id for e in entries}
    categories = {e.category for e in entries}
    accepted = sum((c for course, c in passed.items() if course in in_regulation), ZERO)
    accepted += sum((c for course, c in credited.items() if course in in_regulation), ZERO)
    accepted += sum((t.approved_credits for t in transfers if not t.course_id and t.category in categories), ZERO)
    done = set(passed) | set(credited)
    courses, buckets = [], {"in_progress": ZERO, "planned": ZERO}
    for entry in entries:
        tries = [a for a in attempts if a.course_id == entry.course_id]
        if entry.course_id in done:
            state = "completed"
        elif entry.course_id in going:
            state = "in_progress"
        elif tries and tries[-1].outcome == Outcome.FAILED:
            state = "failed"
        else:
            state = "planned"
        if state == "in_progress":
            buckets["in_progress"] += entry.course.credits
        elif state != "completed":
            buckets["planned"] += entry.course.credits
        courses.append(
            {
                "code": entry.course.code,
                "title": entry.course.title,
                "credits": str(entry.course.credits),
                "category": entry.category,
                "term": entry.term,
                "status": state,
                "attempts": len(tries),
                "prerequisites_met": all(p.id in done for p in entry.prerequisites.all()),
            }
        )
    required = curriculum.credits_required if curriculum else ZERO
    terms: dict = {}
    for item in attempts:
        terms.setdefault(item.term_id, []).append(item)
    return {
        "advisory": True,
        "note": "Advisory progress against the regulation — not an award or a transcript.",
        "program": {"code": enrollment.program.code, "name": enrollment.program.name}
        if enrollment.program_id
        else None,
        "regulation": f"{enrollment.program.code} {curriculum}" if curriculum else None,
        "repeat_rule": rule,
        "cgpa": shown(average(counted(attempts, rule))),
        "terms": [
            {
                "term": rows[0].term.name,
                "year": rows[0].term.year.code,
                "sgpa": shown(average(counted(rows, rule))),
            }
            for rows in terms.values()
        ],
        "credits": {
            "required": _credits(required),
            "earned": _credits(earned),
            "accepted": _credits(accepted),
            "in_progress": _credits(buckets["in_progress"]),
            "planned": _credits(buckets["planned"]),
            "unmet": _credits(max(required - accepted - buckets["in_progress"], ZERO)),
        },
        "courses": courses,
        "attempts": [attempt_item(a) for a in attempts],
        "transfers": [transfer_item(t) for t in enrollment.transfers.select_related("course")],
    }


def attempt_item(attempt: CourseAttempt) -> dict:
    return {
        "id": str(attempt.id),
        "course": attempt.course.code,
        "title": attempt.course.title,
        "attempt_no": attempt.attempt_no,
        "term": attempt.term.name,
        "year": attempt.term.year.code,
        "credits": str(attempt.credits),
        "outcome": attempt.outcome,
        "outcome_label": attempt.get_outcome_display(),
        "grade_point": str(attempt.grade_point) if attempt.grade_point is not None else None,
    }


def transfer_item(transfer: CreditTransfer) -> dict:
    return {
        "id": str(transfer.id),
        "version": transfer.version,
        "source_institution": transfer.source_institution,
        "source_course": transfer.source_course,
        "source_credits": str(transfer.source_credits),
        "evidence": transfer.evidence,
        "decision": transfer.decision,
        "decision_label": transfer.get_decision_display(),
        "approved_credits": str(transfer.approved_credits) if transfer.approved_credits is not None else None,
        "course": transfer.course.code if transfer.course_id else None,
        "category": transfer.category,
        "awarding_authority": transfer.awarding_authority,
    }
