"""Attendance and assignments (slice 6 S6-06..11). Unmarked is not absent; only eligible roster dates count; a
correction after submitting is approved by someone else and keeps the original mark."""

import datetime as dt
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from academics.models import CourseRegistration, EnrollmentPeriod, Substitution
from academics.offerings import label as offering_label
from academics.teaching import assignments
from accounts.permissions import active_membership, has_perm, today_for
from attendance.models import Assignment, AttendanceCorrection, AttendanceMark, AttendanceSession, Submission
from common import audit
from common.exceptions import Problem
from students.models import Enrollment

MANAGE = "attendance.manage"
WINDOW_DAYS = 7  # how far back a teacher may still take attendance
State = AttendanceSession.State


def _campus(target) -> tuple:
    return ("campus", target.campus_id)


def manages(user, institution, target) -> bool:
    return has_perm(user, institution, MANAGE, _campus(target))


def teaches(user, institution, target, date: dt.date | None = None) -> bool:
    """An assignment in effect for the section/offering, or covering one of its lessons that day."""
    kind = "section" if target.__class__.__name__ == "Section" else "offering"
    if assignments(user, institution).filter(**{kind: target}).exists():
        return True
    membership = active_membership(user, institution)
    covers = Substitution.objects.filter(teacher=membership, **{f"slot__{kind}": target})
    return membership is not None and covers.filter(**({"date": date} if date else {})).exists()


def _scope(target) -> dict:
    return {"section": target} if target.__class__.__name__ == "Section" else {"offering": target}


def label(target) -> str:
    return target.code if target.__class__.__name__ == "Section" else offering_label(target)


def roster(target, date: dt.date) -> list[Enrollment]:
    """Who belongs on the register that day (S6-07): placed in the section / registered for the offering, and enrolled
    on that date."""
    if target.__class__.__name__ == "Section":
        ids = EnrollmentPeriod.objects.filter(section=target, state=EnrollmentPeriod.State.ACTIVE).values(
            "enrollment_id"
        )
    else:
        ids = CourseRegistration.objects.filter(offering=target, state=CourseRegistration.State.REGISTERED).values(
            "enrollment_id"
        )
    rows = Enrollment.objects.filter(pk__in=ids, entry_date__lte=date).filter(
        Q(exit_date__isnull=True) | Q(exit_date__gt=date)
    )
    return list(rows.select_related("student__person").order_by("student__number"))


def open_session(user, institution, target, date: dt.date, slot=None) -> tuple[AttendanceSession, bool]:
    manager = manages(user, institution, target)
    if not (manager or teaches(user, institution, target, date)):
        raise NotFound()
    today = today_for(institution)
    if date > today or (not manager and date < today - dt.timedelta(days=WINDOW_DAYS)):
        raise ValidationError({"date": [f"Take attendance for today or the last {WINDOW_DAYS} days."]})
    with transaction.atomic():
        session, made = AttendanceSession.objects.get_or_create(
            institution=institution, date=date, slot=slot, **_scope(target), defaults={"taken_by": user}
        )
        return session, made


def _target(session: AttendanceSession):
    return session.section or session.offering


def _check(user, session: AttendanceSession) -> None:
    target = _target(session)
    if not (manages(user, session.institution, target) or teaches(user, session.institution, target, session.date)):
        raise NotFound()


def save_marks(user, session: AttendanceSession, version: int, marks: list[dict]) -> AttendanceSession:
    _check(user, session)
    with transaction.atomic():
        session = AttendanceSession.objects.select_for_update().get(pk=session.pk)
        session.check_version(version)
        if session.state != State.DRAFT:
            raise Problem(409, "invalid_transition", "Submitted attendance changes only by an approved correction.")
        eligible = {str(e.student_id): e for e in roster(_target(session), session.date)}
        if strangers := [m["student"] for m in marks if str(m["student"]) not in eligible]:
            raise ValidationError({"marks": [f"{len(strangers)} student(s) are not on this register that day."]})
        for item in marks:
            AttendanceMark.objects.update_or_create(
                session=session,
                enrollment=eligible[str(item["student"])],
                defaults={"code": item["code"], "reason": item.get("reason", "")},
            )
        session.taken_by = user
        session.save()
        return session


def submit(user, session: AttendanceSession, version: int) -> AttendanceSession:
    _check(user, session)
    with transaction.atomic():
        session = AttendanceSession.objects.select_for_update().get(pk=session.pk)
        session.check_version(version)
        if session.state != State.DRAFT:
            return session  # submitting twice changes nothing
        session.state, session.submitted_at = State.SUBMITTED, timezone.now()
        session.save()
        what = f"Attendance for {label(_target(session))} on {session.date} submitted"
        audit.log(user, "attendance.submitted", session, what, institution=session.institution)
        return session


def lock(user, session: AttendanceSession, version: int) -> AttendanceSession:
    if not manages(user, session.institution, _target(session)):
        raise PermissionDenied("Only an attendance manager locks attendance.")
    with transaction.atomic():
        session = AttendanceSession.objects.select_for_update().get(pk=session.pk)
        session.check_version(version)
        if session.state != State.SUBMITTED:
            raise Problem(409, "invalid_transition", "Only submitted attendance can be locked.")
        session.state, session.locked_at = State.LOCKED, timezone.now()
        session.save()
        return session


def request_correction(user, mark: AttendanceMark, code: str, reason: str) -> AttendanceCorrection:
    session = mark.session
    _check(user, session)
    if session.state == State.DRAFT:
        raise Problem(
            409, "invalid_transition", "Change a saved draft directly; corrections are for submitted attendance."
        )
    if code == mark.code:
        raise ValidationError({"code": ["That is already the mark."]})
    correction = AttendanceCorrection.objects.create(
        institution=session.institution,
        mark=mark,
        previous_code=mark.code,
        new_code=code,
        reason=reason,
        requested_by=user,
    )
    return correction


def decide_correction(user, correction: AttendanceCorrection, approve: bool) -> AttendanceCorrection:
    target = _target(correction.mark.session)
    if not manages(user, correction.institution, target) or correction.requested_by_id == user.id:
        raise PermissionDenied("Someone else who manages attendance decides this correction.")
    with transaction.atomic():
        correction = AttendanceCorrection.objects.select_for_update().select_related("mark").get(pk=correction.pk)
        if correction.state != AttendanceCorrection.State.REQUESTED:
            raise Problem(409, "invalid_transition", "This correction has already been decided.")
        correction.state = AttendanceCorrection.State.APPROVED if approve else AttendanceCorrection.State.REJECTED
        correction.decided_by, correction.decided_at = user, timezone.now()
        correction.save()
        if approve:
            mark = correction.mark
            mark.code, mark.reason = correction.new_code, correction.reason
            mark.save()
        audit.log(
            user,
            "attendance.corrected" if approve else "attendance.correction_rejected",
            correction.mark.enrollment.student,
            f"{correction.previous_code} → {correction.new_code} on {correction.mark.session.date}",
            institution=correction.institution,
            changes={"code": {"from": correction.previous_code, "to": correction.new_code}},
        )
        return correction


def summary(enrollments) -> dict:
    """Counts over submitted and locked sessions only; unmarked days are not absences (S6-06)."""
    marks = AttendanceMark.objects.filter(
        enrollment__in=enrollments, session__state__in=(State.SUBMITTED, State.LOCKED)
    ).select_related("session__section", "session__offering__course")
    counts = {code: 0 for code in AttendanceMark.Code.values}
    absences = []
    for mark in marks.order_by("session__date"):
        counts[mark.code] += 1
        if mark.code == AttendanceMark.Code.ABSENT:
            absences.append({"date": mark.session.date, "label": label(_target(mark.session)), "code": mark.code})
    counted = sum(counts[c] for c in AttendanceMark.DENOMINATOR)
    attended = sum(counts[c] for c in AttendanceMark.NUMERATOR)
    percentage = (Decimal(attended) * 100 / counted).quantize(Decimal("0.1")) if counted else None
    return {
        **counts,
        "counted": counted,
        "percentage": str(percentage) if percentage is not None else None,
        "absences": absences,
    }


def session_item(session: AttendanceSession) -> dict:
    target = _target(session)
    marks = {m.enrollment_id: m for m in session.marks.all()}
    rows = roster(target, session.date)
    return {
        "id": str(session.id),
        "version": session.version,
        "state": session.state,
        "state_label": session.get_state_display(),
        "date": session.date,
        "target": {
            "kind": "section" if session.section_id else "offering",
            "id": str(target.id),
            "label": label(target),
        },
        "submitted_at": session.submitted_at,
        "roster": [
            {
                "student": {
                    "id": str(e.student_id),
                    "number": e.student.number,
                    "full_name": e.student.person.full_name,
                },
                "code": marks[e.id].code if e.id in marks else None,
                "reason": marks[e.id].reason if e.id in marks else "",
                "mark": str(marks[e.id].id) if e.id in marks else None,
            }
            for e in rows
        ],
        "unmarked": sum(1 for e in rows if e.id not in marks),
    }


def correction_item(c: AttendanceCorrection) -> dict:
    session = c.mark.session
    return {
        "id": str(c.id),
        "state": c.state,
        "previous_code": c.previous_code,
        "new_code": c.new_code,
        "reason": c.reason,
        "date": session.date,
        "label": label(_target(session)),
        "student": {
            "number": c.mark.enrollment.student.number,
            "full_name": c.mark.enrollment.student.person.full_name,
        },
        "requested_by": c.requested_by.full_name,
    }


# Assignments (S6-11)


def post_assignment(user, institution, target, data: dict) -> Assignment:
    if not teaches(user, institution, target):
        raise NotFound()
    made = Assignment.objects.create(institution=institution, created_by=user, **_scope(target), **data)
    audit.log(user, "assignment.posted", made, f"{made.title} for {label(target)}", institution=institution)
    return made


def can_see(user, assignment: Assignment) -> bool:
    target = assignment.section or assignment.offering
    return teaches(user, assignment.institution, target) or manages(user, assignment.institution, target)


def for_student(enrollment: Enrollment):
    sections = EnrollmentPeriod.objects.filter(enrollment=enrollment, state=EnrollmentPeriod.State.ACTIVE).values(
        "section_id"
    )
    offerings = CourseRegistration.objects.filter(
        enrollment=enrollment, state=CourseRegistration.State.REGISTERED
    ).values("offering_id")
    return Assignment.objects.filter(Q(section_id__in=sections) | Q(offering_id__in=offerings))


def hand_in(enrollment: Enrollment, assignment: Assignment, text: str) -> Submission:
    if not for_student(enrollment).filter(pk=assignment.pk).exists():
        raise NotFound()
    with transaction.atomic():
        found = Submission.objects.select_for_update().filter(assignment=assignment, enrollment=enrollment).first()
        if found is not None and found.feedback_at is not None:
            raise Problem(409, "invalid_transition", "This has been marked; it can't be changed now.")
        now = timezone.now()
        found = found or Submission(assignment=assignment, enrollment=enrollment)
        found.text, found.submitted_at, found.late = text, now, now > assignment.due_at
        found.save()
        return found


def give_feedback(user, submission: Submission, feedback: str) -> Submission:
    if not can_see(user, submission.assignment):
        raise NotFound()
    submission.feedback, submission.feedback_by, submission.feedback_at = feedback, user, timezone.now()
    submission.save()
    return submission


def assignment_item(a: Assignment, submissions: bool = False, enrollment: Enrollment | None = None) -> dict:
    target = a.section or a.offering
    item = {
        "id": str(a.id),
        "title": a.title,
        "instructions": a.instructions,
        "due_at": a.due_at,
        "target": {"kind": "section" if a.section_id else "offering", "id": str(target.id), "label": label(target)},
    }
    if submissions:
        item["submissions"] = [
            {
                "id": str(s.id),
                "student": {"number": s.enrollment.student.number, "full_name": s.enrollment.student.person.full_name},
                "text": s.text,
                "submitted_at": s.submitted_at,
                "late": s.late,
                "feedback": s.feedback,
            }
            for s in a.submissions.select_related("enrollment__student__person").order_by("enrollment__student__number")
        ]
    if enrollment is not None:
        mine = a.submissions.filter(enrollment=enrollment).first()
        item["submission"] = (
            {"text": mine.text, "submitted_at": mine.submitted_at, "late": mine.late, "feedback": mine.feedback}
            if mine
            else None
        )
    return item
