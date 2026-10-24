"""Course registration (slice 5c S5C-01..08, WF-ACA §6.2, API §4.3). Every failed rule has its own code; an adviser's
override lets one student past one rule for one offering, never past capacity. Seats are claimed with the offerings
locked in id order, so the last seat goes to exactly one request, and a lecture and its lab commit together."""

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.models import (
    CourseAttempt,
    CourseOffering,
    CourseRegistration,
    CreditTransfer,
    Hold,
    RegistrationOverride,
    RegistrationWindow,
    Term,
)
from academics.offerings import label
from accounts.permissions import WHOLE, has_perm, today_for
from common import audit
from common.exceptions import Problem
from students.models import Enrollment, Student

MANAGE = "registration.manage"
OVERRIDE = "registration.override"
State = CourseRegistration.State

MESSAGES = {
    "window_closed": "Registration for this term is not open",
    "hold": "A hold stops registration",
    "offering_closed": "This offering is not open for registration",
    "not_in_regulation": "This course is not in the student's regulation",
    "prerequisite": "A prerequisite has not been passed",
    "already_passed": "This course has already been passed",
    "credit_limit": "This would go over the term's credit limit",
    "linked_section": "A lecture and its lab register together",
}


def can_manage(actor, student: Student) -> bool:
    return has_perm(actor, student.institution, MANAGE, student.scope)


def _require(actor, student: Student, perm: str = MANAGE) -> None:
    if not has_perm(actor, student.institution, perm, student.scope):
        raise PermissionDenied("Your role does not cover this student's registration.")


def _enrollment(student: Student, lock: bool = False) -> Enrollment:
    rows = Enrollment.objects.filter(student=student, status=Enrollment.Status.ACTIVE).select_related("curriculum")
    enrollment = (rows.select_for_update(of=("self",)) if lock else rows).first()
    if student.status != Student.Status.ACTIVE or enrollment is None:
        raise Problem(422, "not_enrolled", f"{student.number} is not enrolled now.")
    if enrollment.curriculum_id is None:
        raise Problem(422, "no_regulation", f"{student.number} has no regulation pinned; set it on their record first.")
    return enrollment


def passed_courses(enrollment: Enrollment) -> set:
    """Courses passed here, or credited from elsewhere as that course."""
    attempts = enrollment.attempts.filter(outcome=CourseAttempt.Outcome.PASSED).values_list("course_id", flat=True)
    transfers = enrollment.transfers.filter(decision=CreditTransfer.Decision.APPROVED, course__isnull=False)
    return set(attempts) | set(transfers.values_list("course_id", flat=True))


def _labs(offering: CourseOffering) -> list:
    return [lab for lab in offering.linked.all() if lab.status != CourseOffering.Status.CANCELLED]


def _has_links(offering: CourseOffering) -> bool:
    return bool(offering.linked_to_id or _labs(offering))


def _failures(enrollment: Enrollment, window: RegistrationWindow, offerings: list, chosen: set, promoting=False):
    """{offering id: [failed rule codes]} for the given offerings, with `chosen` the offerings the student would then
    hold (for links). Capacity is checked separately, under the locks."""
    today = today_for(enrollment.institution)
    entries = {e.course_id: e for e in enrollment.curriculum.courses.prefetch_related("prerequisites")}
    passed = passed_courses(enrollment)
    held = Hold.objects.filter(student_id=enrollment.student_id, lifted_on__isnull=True).exists()
    active = enrollment.registrations.filter(state__in=CourseRegistration.ACTIVE).select_related("offering__course")
    holding = {r.offering_id for r in active}
    term_credits = sum(r.offering.course.credits for r in active if r.offering.term_id == window.term_id)
    new_credits = sum(o.course.credits for o in offerings if o.id not in holding)
    found = {}
    for offering in offerings:
        codes = []
        if offering.status != CourseOffering.Status.OPEN:
            codes.append("offering_closed")
        if not promoting and not window.opens_on <= today <= window.closes_on:
            codes.append("window_closed")
        if held:
            codes.append("hold")
        entry = entries.get(offering.course_id)
        if entry is None:
            codes.append("not_in_regulation")
        elif any(p.id not in passed for p in entry.prerequisites.all()):
            codes.append("prerequisite")
        if offering.course_id in passed:
            codes.append("already_passed")
        if term_credits + new_credits > window.max_credits:
            codes.append("credit_limit")
        labs = _labs(offering)
        lecture_missing = offering.linked_to_id and offering.linked_to_id not in chosen
        if lecture_missing or (labs and sum(lab.id in chosen for lab in labs) != 1):
            codes.append("linked_section")
        found[offering.id] = codes
    return found


def _usable_overrides(student: Student, offerings: list, registration: CourseRegistration | None = None) -> list:
    today = today_for(student.institution)
    rows = RegistrationOverride.objects.filter(student=student, offering__in=offerings, expires_on__gte=today)
    return list(rows.filter(used_by=registration) if registration else rows.filter(used_by__isnull=True))


def _seated(offering: CourseOffering) -> int:
    return offering.registrations.filter(state__in=CourseRegistration.SEATED).count()


def _attempt(registration: CourseRegistration) -> CourseAttempt:
    course = registration.offering.course
    previous = registration.enrollment.attempts.filter(course=course).aggregate(n=Max("attempt_no"))["n"] or 0
    return CourseAttempt.objects.create(
        institution=registration.institution,
        enrollment=registration.enrollment,
        course=course,
        attempt_no=previous + 1,
        registration=registration,
        term=registration.offering.term,
        credits=course.credits,
    )


def _window(term_id) -> RegistrationWindow:
    window = RegistrationWindow.objects.filter(term_id=term_id).first()
    if window is None:
        raise Problem(422, "window_closed", "Registration for this term has not been set up.")
    return window


def register(actor, student: Student, offering_ids: list, waitlist: bool = False):
    """The registrations for these offerings, made together or not at all: (registrations, made now?)."""
    ids = list(dict.fromkeys(offering_ids))
    with transaction.atomic():
        enrollment = _enrollment(student, lock=True)  # one request per student at a time
        offerings = list(
            CourseOffering.objects.select_for_update(of=("self",))
            .filter(institution=student.institution, pk__in=ids)
            .select_related("course", "term", "linked_to__course")
            .prefetch_related("linked")
            .order_by("pk")
        )
        if not ids or len(offerings) != len(ids):
            raise ValidationError({"offerings": ["Choose offerings of this institution."]})
        if len({o.term_id for o in offerings}) > 1:
            raise ValidationError({"offerings": ["Choose offerings of one term."]})
        window = _window(offerings[0].term_id)
        existing = {
            r.offering_id: r
            for r in enrollment.registrations.filter(state__in=CourseRegistration.ACTIVE, offering__in=offerings)
        }
        if len(existing) == len(offerings):
            return [existing[o.id] for o in offerings], False  # asked again: the same registrations
        new = [o for o in offerings if o.id not in existing]
        holding = set(
            enrollment.registrations.filter(state__in=CourseRegistration.ACTIVE).values_list("offering_id", flat=True)
        )
        failures = _failures(enrollment, window, new, holding | {o.id for o in offerings})
        overrides = _usable_overrides(student, new)
        used = []
        for offering in new:
            for override in overrides:
                if override.offering_id == offering.id and override.rule in failures[offering.id]:
                    failures[offering.id].remove(override.rule)
                    used.append(override)
        refused = [(o, code) for o in new for code in failures[o.id]]
        if refused:
            raise Problem(
                422,
                "registration_refused",
                "; ".join(f"{label(o)}: {MESSAGES[code]}" for o, code in refused) + ".",
                failures=[
                    {"offering": label(o), "offering_id": str(o.id), "code": code, "message": MESSAGES[code]}
                    for o, code in refused
                ],
            )
        full = [o for o in new if _seated(o) >= o.capacity]
        if not full:
            state = State.PENDING if window.needs_approval else State.REGISTERED
        elif waitlist and len(new) == 1 and not _has_links(new[0]):
            state = State.WAITLISTED
        else:
            raise Problem(409, "capacity_exhausted", f"{label(full[0])} has no seats left.", offering=label(full[0]))
        made = []
        for offering in new:
            registration = CourseRegistration.objects.create(
                institution=student.institution,
                enrollment=enrollment,
                offering=offering,
                state=state,
                curriculum=enrollment.curriculum,
                window=window,
                window_version=window.version,
                requested_by=actor,
            )
            for override in used:
                if override.offering_id == offering.id:
                    override.used_by = registration
                    override.save(update_fields=["used_by"])
            if state == State.REGISTERED:
                _attempt(registration)
            made.append(registration)
        audit.log(
            actor,
            "registration.requested",
            student,
            f"{student.number}: {', '.join(label(o) for o in new)} {state.label.lower()}",
            institution=student.institution,
            changes={"offerings": [label(o) for o in new], "state": state, "overrides": [o.rule for o in used]},
        )
        return [existing.get(o.id) or next(r for r in made if r.offering_id == o.id) for o in offerings], True


def _group(registration: CourseRegistration, states) -> list:
    """The registration with its linked lecture or lab of the same student: they change together."""
    offering = registration.offering
    linked = {offering.id, offering.linked_to_id, *[lab.id for lab in offering.linked.all()]} - {None}
    rows = registration.enrollment.registrations.filter(offering_id__in=linked, state__in=states)
    return list(rows.select_for_update().select_related("offering__course", "offering__term", "enrollment__student"))


def _locked(registration: CourseRegistration, version: int) -> CourseRegistration:
    found = (
        CourseRegistration.objects.select_for_update()
        .select_related("enrollment__student", "offering")
        .get(pk=registration.pk)
    )
    found.check_version(version)
    return found


def _decide(actor, registration: CourseRegistration, to: str, code: str = "") -> None:
    registration.state, registration.reason_code = to, code
    registration.decided_by, registration.decided_at = actor, timezone.now()
    registration.save()


def approve(actor, registration: CourseRegistration, version: int) -> CourseRegistration:
    _require(actor, registration.enrollment.student)
    with transaction.atomic():
        registration = _locked(registration, version)
        if registration.state != State.PENDING:
            raise Problem(409, "invalid_transition", "Only a registration waiting for approval can be approved.")
        for row in _group(registration, [State.PENDING]):
            _decide(actor, row, State.REGISTERED)
            _attempt(row)
        _log(actor, registration, "approved")
        registration.refresh_from_db()
        return registration


def reject(actor, registration: CourseRegistration, version: int) -> CourseRegistration:
    _require(actor, registration.enrollment.student)
    with transaction.atomic():
        registration = _locked(registration, version)
        if registration.state not in (State.PENDING, State.WAITLISTED):
            raise Problem(409, "invalid_transition", "Only a waiting registration can be rejected.")
        rows = _group(registration, [State.PENDING, State.WAITLISTED])
        for row in rows:
            _decide(actor, row, State.REJECTED, "rejected")
        _promote_all(actor, rows)
        _log(actor, registration, "rejected")
        registration.refresh_from_db()
        return registration


def drop(actor, registration: CourseRegistration, version: int, by_student: bool = False) -> CourseRegistration:
    """Dropped until the window's drop deadline (the attempt goes); withdrawn after it (the attempt stays as W).
    Students drop for themselves only until the deadline."""
    student = registration.enrollment.student
    if not by_student:
        _require(actor, student)
    with transaction.atomic():
        registration = _locked(registration, version)
        if registration.state not in CourseRegistration.ACTIVE:
            raise Problem(409, "invalid_transition", "This registration is no longer active.")
        late = today_for(student.institution) > registration.window.drop_until
        if late and by_student and registration.state == State.REGISTERED:
            raise Problem(409, "window_closed", "The drop deadline has passed; ask the office to withdraw you.")
        rows = _group(registration, CourseRegistration.ACTIVE)
        for row in rows:
            attempt = CourseAttempt.objects.filter(registration=row).first()
            if attempt is not None and attempt.outcome != CourseAttempt.Outcome.IN_PROGRESS:
                raise Problem(409, "invalid_transition", f"{label(row.offering)} already has an outcome recorded.")
            if row.state == State.REGISTERED and late:
                _decide(actor, row, State.WITHDRAWN)
                attempt.outcome = CourseAttempt.Outcome.WITHDRAWN
                attempt.save(update_fields=["outcome"])
            else:
                _decide(actor, row, State.DROPPED)
                if attempt is not None:
                    attempt.delete()  # dropped in time: as if never taken
        _promote_all(actor, rows)
        _log(actor, registration, "dropped" if not late else "withdrawn")
        registration.refresh_from_db()
        return registration


def _promote_all(actor, rows: list) -> None:
    for row in rows:
        _promote(actor, row.offering)


def _promote(actor, offering: CourseOffering) -> None:
    """Fill freed seats from the waitlist, oldest first; whoever no longer qualifies is rejected with the rule."""
    offering = CourseOffering.objects.select_for_update().select_related("course").get(pk=offering.pk)
    window = _window(offering.term_id)
    while _seated(offering) < offering.capacity:
        waiting = offering.registrations.filter(state=State.WAITLISTED).order_by("created_at")
        nxt = waiting.select_related("enrollment__student", "enrollment__curriculum").first()
        if nxt is None:
            return
        enrollment = nxt.enrollment
        if enrollment.status != Enrollment.Status.ACTIVE or enrollment.student.status != Student.Status.ACTIVE:
            codes = ["not_enrolled"]
        else:
            holding = set(
                enrollment.registrations.filter(state__in=CourseRegistration.ACTIVE).values_list(
                    "offering_id", flat=True
                )
            )
            codes = _failures(enrollment, window, [offering], holding, promoting=True)[offering.id]
            covered = {o.rule for o in _usable_overrides(enrollment.student, [offering], nxt)}
            codes = [code for code in codes if code not in covered]
        if codes:
            _decide(actor, nxt, State.REJECTED, codes[0])
            continue
        _decide(actor, nxt, State.PENDING if window.needs_approval else State.REGISTERED)
        if nxt.state == State.REGISTERED:
            _attempt(nxt)
        _log(actor, nxt, "promoted from the waitlist")


def _log(actor, registration: CourseRegistration, what: str) -> None:
    student = registration.enrollment.student
    audit.log(
        actor,
        f"registration.{what.split()[0]}",
        student,
        f"{student.number}: {label(registration.offering)} {what}",
        institution=student.institution,
    )


def grant_override(actor, student: Student, offering: CourseOffering, data: dict) -> RegistrationOverride:
    _require(actor, student, OVERRIDE)
    if data["expires_on"] < today_for(student.institution):
        raise ValidationError({"expires_on": ["Choose today or a later day."]})
    enrollment = _enrollment(student)
    window = RegistrationWindow.objects.filter(term_id=offering.term_id).first()
    override = RegistrationOverride.objects.create(
        institution=student.institution,
        student=student,
        offering=offering,
        rule=data["rule"],
        reason=data["reason"],
        expires_on=data["expires_on"],
        granted_by=actor,
        curriculum=enrollment.curriculum,
        window_version=window.version if window else None,
    )
    audit.log(
        actor,
        "registration.override_granted",
        student,
        f"{student.number} may pass {data['rule']} for {label(offering)}: {data['reason']}",
        institution=student.institution,
    )
    return override


def place_hold(actor, student: Student, data: dict) -> Hold:
    _require(actor, student)
    hold = Hold.objects.create(
        institution=student.institution,
        placed_by=actor,
        placed_on=today_for(student.institution),
        student=student,
        **data,
    )
    audit.log(
        actor,
        "student.hold_placed",
        student,
        f"Hold on {student.number}: {hold.reason}",
        institution=student.institution,
    )
    return hold


def lift_hold(actor, hold: Hold) -> Hold:
    _require(actor, hold.student)
    if hold.lifted_on is None:
        hold.lifted_by, hold.lifted_on = actor, today_for(hold.institution)
        hold.save(update_fields=["lifted_by", "lifted_on"])
        audit.log(
            actor,
            "student.hold_lifted",
            hold.student,
            f"Hold on {hold.student.number} lifted",
            institution=hold.institution,
        )
    return hold


def save_window(actor, institution, window: RegistrationWindow | None, data: dict, version: int | None = None):
    if not has_perm(actor, institution, MANAGE, WHOLE):
        raise PermissionDenied("Only someone who manages registration for the whole institution can change this.")
    with transaction.atomic():
        if window is not None:
            window = RegistrationWindow.objects.select_for_update().get(pk=window.pk)
            window.check_version(version)
        else:
            term = Term.objects.filter(pk=data.pop("term"), year__institution=institution).first()
            if term is None or RegistrationWindow.objects.filter(term=term).exists():
                raise ValidationError({"term": ["Choose a term of this institution without a registration window."]})
            window = RegistrationWindow(institution=institution, term=term)
        for name, value in data.items():
            setattr(window, name, value)
        if window.closes_on < window.opens_on:
            raise ValidationError({"closes_on": ["Close on or after the opening day."]})
        if window.drop_until < window.opens_on:
            raise ValidationError({"drop_until": ["The drop deadline can't be before registration opens."]})
        window.save()
        audit.log(
            actor,
            "registration.window_saved",
            window,
            f"Registration window for {window.term.name} saved",
            institution=institution,
        )
        return window


def problems(student: Student, offering: CourseOffering) -> list:
    """What would stop the student registering for this offering alone, after overrides (for the course finder; links
    are shown as pairs, so they are left out)."""
    enrollment = _enrollment(student)
    window = _window(offering.term_id)
    holding = set(
        enrollment.registrations.filter(state__in=CourseRegistration.ACTIVE).values_list("offering_id", flat=True)
    )
    codes = _failures(enrollment, window, [offering], holding | {offering.id})[offering.id]
    covered = {o.rule for o in _usable_overrides(student, [offering])}
    return [code for code in codes if code not in covered and code != "linked_section"]


def window_item(window: RegistrationWindow) -> dict:
    today = today_for(window.institution)
    return {
        "id": str(window.id),
        "version": window.version,
        "term": window.term.name,
        "term_id": str(window.term_id),
        "year": window.term.year.code,
        "opens_on": window.opens_on,
        "closes_on": window.closes_on,
        "drop_until": window.drop_until,
        "max_credits": str(window.max_credits),
        "needs_approval": window.needs_approval,
        "open": window.opens_on <= today <= window.closes_on,
    }


def registration_item(registration: CourseRegistration) -> dict:
    offering, student = registration.offering, registration.enrollment.student
    attempt = CourseAttempt.objects.filter(registration=registration).first()
    return {
        "id": str(registration.id),
        "version": registration.version,
        "state": registration.state,
        "state_label": registration.get_state_display(),
        "reason_code": registration.reason_code,
        "offering": {
            "id": str(offering.id),
            "label": label(offering),
            "title": offering.course.title,
            "credits": str(offering.course.credits),
            "term": offering.term.name,
        },
        "student": {"id": str(student.id), "number": student.number, "full_name": student.person.full_name},
        "attempt_no": attempt.attempt_no if attempt else None,
        "regulation": str(registration.curriculum) if registration.curriculum_id else None,
        "window_version": registration.window_version,
        "overrides": [
            {
                "rule": o.rule,
                "reason": o.reason,
                "granted_by": o.granted_by.full_name,
                "regulation": str(o.curriculum) if o.curriculum_id else None,
            }
            for o in registration.overrides.select_related("granted_by", "curriculum")
        ],
        "created_at": registration.created_at,
    }


def hold_item(hold: Hold) -> dict:
    return {
        "id": str(hold.id),
        "kind": hold.kind,
        "kind_label": hold.get_kind_display(),
        "reason": hold.reason,
        "placed_on": hold.placed_on,
        "placed_by": hold.placed_by.full_name,
        "lifted_on": hold.lifted_on,
    }


def override_item(override: RegistrationOverride) -> dict:
    return {
        "id": str(override.id),
        "rule": override.rule,
        "reason": override.reason,
        "offering": label(override.offering),
        "expires_on": override.expires_on,
        "granted_by": override.granted_by.full_name,
        "regulation": str(override.curriculum) if override.curriculum_id else None,
        "used": override.used_by_id is not None,
    }
