"""Assessments to published results and issued documents (slice 7 S7-01..12, WF-EXM §8, EX-02).

Totals are worked out exactly (Σ score ÷ maximum × weight) and rounded only for display; absent, withheld, exempt and
missing are states, never zeroes. Published results never change: a correction is the next revision."""

import hashlib
import json
import secrets
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from academics.models import CourseAttempt, CourseRegistration, EnrollmentPeriod, Section, Subject, Term
from accounts.permissions import WHOLE, has_perm
from attendance import services as attendance
from common import audit
from common.exceptions import Problem
from results.models import (
    Assessment,
    AttainmentRun,
    Candidate,
    CourseOutcome,
    IssuedDocument,
    Mark,
    OutcomeMapping,
    PromotionDecision,
    ResultVersion,
    RevisionCase,
    Scheme,
    SchemeComponent,
)
from students.models import Enrollment, Student

MANAGE, MODERATE, PUBLISH = "assessment.manage", "results.moderate", "results.publish"
HUNDRED = Decimal(100)
State = Assessment.State


def _require(actor, institution, perm: str, scope=WHOLE) -> None:
    if not has_perm(actor, institution, perm, scope):
        raise PermissionDenied("Your role does not allow this step.")


# Schemes (S7-01)


def save_scheme(actor, institution, scheme: Scheme | None, data: dict, version: int | None = None) -> Scheme:
    _require(actor, institution, MANAGE)
    with transaction.atomic():
        if scheme is not None:
            scheme = Scheme.objects.select_for_update().get(pk=scheme.pk)
            scheme.check_version(version)
            if scheme.status != Scheme.Status.DRAFT:
                raise Problem(409, "invalid_transition", "A published scheme never changes; revise it instead.")
        else:
            scheme = Scheme(institution=institution)
        components = data.pop("components", None)
        for name, value in data.items():
            setattr(scheme, name, value)
        scheme.save()
        if components is not None:
            scheme.components.all().delete()
            for order, item in enumerate(components):
                SchemeComponent.objects.create(scheme=scheme, order=order, **item)
        return scheme


def publish_scheme(actor, scheme: Scheme, version: int) -> Scheme:
    _require(actor, scheme.institution, MANAGE)
    with transaction.atomic():
        scheme = Scheme.objects.select_for_update().get(pk=scheme.pk)
        scheme.check_version(version)
        if scheme.status != Scheme.Status.DRAFT:
            raise Problem(409, "invalid_transition", "Only a draft scheme is published.")
        components = list(scheme.components.all())
        if not components:
            raise ValidationError({"components": ["Add at least one component."]})
        if sum((c.weight for c in components), Decimal(0)) != HUNDRED:
            raise ValidationError({"components": ["The weights must add up to 100."]})
        if not scheme.bands or min(Decimal(b["min"]) for b in scheme.bands) != 0:
            raise ValidationError({"bands": ["Grade bands must start from 0."]})
        scheme.status, scheme.published_by, scheme.published_at = Scheme.Status.PUBLISHED, actor, timezone.now()
        scheme.save()
        return scheme


def revise_scheme(actor, scheme: Scheme) -> Scheme:
    _require(actor, scheme.institution, MANAGE)
    with transaction.atomic():
        latest = Scheme.objects.select_for_update().filter(family=scheme.family).aggregate(n=Max("revision"))["n"]
        if draft := Scheme.objects.filter(family=scheme.family, status=Scheme.Status.DRAFT).first():
            return draft
        made = Scheme.objects.create(
            institution=scheme.institution, family=scheme.family, revision=latest + 1, name=scheme.name,
            pass_percent=scheme.pass_percent, decimals=scheme.decimals, bands=scheme.bands,
        )  # fmt: skip
        for comp in scheme.components.all():
            SchemeComponent.objects.create(
                scheme=made, name=comp.name, max_marks=comp.max_marks, weight=comp.weight,
                min_percent=comp.min_percent, order=comp.order,
            )  # fmt: skip
        return made


# Calculation (S7-05, EX-02)


def calculate(scheme: Scheme, marks: dict) -> dict:
    """marks: {component id: {"status": …, "score": Decimal | None}} for every component. Exact; rounded for display."""
    components = list(scheme.components.all())
    statuses = {marks[c.id]["status"] for c in components}
    if Mark.Status.ABSENT in statuses or Mark.Status.WITHHELD in statuses:
        outcome = ResultVersion.Outcome.WITHHELD if Mark.Status.WITHHELD in statuses else ResultVersion.Outcome.ABSENT
        return {"total": None, "shown": "", "grade": "", "point": None, "outcome": outcome, "failed": []}
    counted = [c for c in components if marks[c.id]["status"] == Mark.Status.SCORED]
    weights = sum((c.weight for c in counted), Decimal(0))
    raw = sum((marks[c.id]["score"] / c.max_marks * c.weight for c in counted), Decimal(0))
    total = raw * HUNDRED / weights if weights else Decimal(0)  # exempt components leave the rest scaled to 100
    failed = [
        c.name
        for c in counted
        if c.min_percent is not None and marks[c.id]["score"] * HUNDRED / c.max_marks < c.min_percent
    ]
    passed = total >= scheme.pass_percent and not failed
    bands = sorted(scheme.bands, key=lambda b: Decimal(b["min"]), reverse=True)
    band = next(b for b in bands if total >= Decimal(b["min"])) if passed else bands[-1]
    quantum = Decimal(1).scaleb(-scheme.decimals)
    return {
        "total": total,
        "shown": str(total.quantize(quantum, rounding=ROUND_HALF_UP)),
        "grade": band["grade"],
        "point": Decimal(band["point"]),
        "outcome": ResultVersion.Outcome.PASSED if passed else ResultVersion.Outcome.FAILED,
        "failed": failed,
    }


# Assessments (S7-02..04)


def _target(a: Assessment):
    return a.section or a.offering


def can_evaluate(user, a: Assessment) -> bool:
    target = _target(a)
    return has_perm(user, a.institution, MANAGE, WHOLE) or attendance.teaches(user, a.institution, target)


def can_see(user, a: Assessment) -> bool:
    return can_evaluate(user, a) or any(has_perm(user, a.institution, p, WHOLE) for p in (MODERATE, PUBLISH))


def create_assessment(actor, institution, data: dict) -> Assessment:
    _require(actor, institution, MANAGE)
    scheme = Scheme.objects.filter(institution=institution, pk=data["scheme"], status=Scheme.Status.PUBLISHED).first()
    if scheme is None:
        raise ValidationError({"scheme": ["Choose a published scheme."]})
    term = Term.objects.filter(year__institution=institution, pk=data["term"]).first()
    if term is None:
        raise ValidationError({"term": ["Choose a term."]})
    a = Assessment(institution=institution, scheme=scheme, term=term, title=data["title"], created_by=actor)
    if data.get("offering"):
        a.offering = institution.offerings.filter(pk=data["offering"], term=term).first()
        if a.offering is None:
            raise ValidationError({"offering": ["Choose an offering of this term."]})
    elif data.get("section"):
        a.section = Section.objects.filter(institution=institution, pk=data["section"], year=term.year).first()
        a.subject = Subject.objects.filter(institution=institution, pk=data.get("subject")).first()
        if a.section is None or a.subject is None:
            raise ValidationError({"section": ["Choose a section of this term's year and a subject."]})
    else:
        raise ValidationError({"section": ["Choose a section and subject, or an offering."]})
    with transaction.atomic():
        a.save()
        if a.offering_id:
            for reg in CourseRegistration.objects.filter(
                offering=a.offering, state=CourseRegistration.State.REGISTERED
            ):
                Candidate.objects.create(assessment=a, enrollment_id=reg.enrollment_id, registration=reg)
        else:
            periods = EnrollmentPeriod.objects.filter(section=a.section, state=EnrollmentPeriod.State.ACTIVE)
            for enrollment_id in periods.values_list("enrollment_id", flat=True):
                Candidate.objects.create(assessment=a, enrollment_id=enrollment_id)
        audit.log(actor, "assessment.created", a, f"{a.title} set up", institution=institution)
        return a


def _locked(a: Assessment, version: int) -> Assessment:
    a = Assessment.objects.select_for_update().select_related("scheme").get(pk=a.pk)
    a.check_version(version)
    return a


def save_marks(actor, a: Assessment, version: int, marks: list[dict]) -> Assessment:
    if not can_evaluate(actor, a):
        raise NotFound()
    with transaction.atomic():
        a = _locked(a, version)
        if a.state != State.DRAFT:
            raise Problem(409, "invalid_transition", "Marks change only while the assessment is a draft.")
        candidates = {str(c.id): c for c in a.candidates.all()}
        components = {str(c.id): c for c in a.scheme.components.all()}
        for item in marks:
            candidate, component = candidates.get(str(item["candidate"])), components.get(str(item["component"]))
            if candidate is None or component is None:
                raise ValidationError({"marks": ["A mark names a student or component outside this assessment."]})
            score = item.get("score") if item["status"] == Mark.Status.SCORED else None
            if item["status"] == Mark.Status.SCORED and (score is None or not 0 <= score <= component.max_marks):
                raise ValidationError({"marks": [f"{component.name} takes a score from 0 to {component.max_marks}."]})
            Mark.objects.update_or_create(
                candidate=candidate, component=component,
                defaults={"score": score, "status": item["status"], "entered_by": actor},
            )  # fmt: skip
        a.save()
        return a


def submit(actor, a: Assessment, version: int) -> Assessment:
    if not can_evaluate(actor, a):
        raise NotFound()
    with transaction.atomic():
        a = _locked(a, version)
        if a.state != State.DRAFT:
            raise Problem(409, "invalid_transition", "Only a draft is submitted.")
        a.state, a.submitted_by, a.returned_reason = State.SUBMITTED, actor, ""
        a.save()
        return a


def moderate(actor, a: Assessment, version: int, back: str | None = None) -> Assessment:
    """Approve submitted marks, or with `back` return them to the evaluator. Never by whoever submitted them."""
    _require(actor, a.institution, MODERATE)
    with transaction.atomic():
        a = _locked(a, version)
        if a.state != State.SUBMITTED:
            raise Problem(409, "invalid_transition", "Only submitted marks are moderated.")
        if a.submitted_by_id == actor.id:
            raise PermissionDenied("Someone other than who submitted the marks moderates them.")
        if back is not None:
            a.state, a.returned_reason = State.DRAFT, back
        else:
            a.state, a.moderated_by = State.MODERATED, actor
        a.save()
        return a


def _marks_of(candidate: Candidate, scheme: Scheme) -> dict | None:
    found = {m.component_id: m for m in candidate.marks.all()}
    if any(c.id not in found for c in scheme.components.all()):
        return None
    return {cid: {"status": m.status, "score": m.score} for cid, m in found.items()}


def _inputs(marks: dict, scheme: Scheme) -> tuple[dict, str]:
    shown = {
        str(k): {"status": v["status"], "score": str(v["score"]) if v["score"] is not None else None}
        for k, v in sorted(marks.items(), key=lambda kv: str(kv[0]))
    }
    inputs = {"scheme": str(scheme.id), "scheme_revision": scheme.revision, "marks": shown}
    return inputs, hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def _record(actor, candidate: Candidate, marks: dict, reason: str = "") -> ResultVersion:
    scheme = candidate.assessment.scheme
    worked = calculate(scheme, marks)
    inputs, digest = _inputs(marks, scheme)
    now = timezone.now()
    previous = candidate.results.filter(superseded_at__isnull=True).first()
    if previous is not None:
        previous.superseded_at = now
        previous.save(update_fields=["superseded_at"])
    version = ResultVersion.objects.create(
        candidate=candidate, revision=(previous.revision + 1) if previous else 1, total=worked["total"],
        shown_total=worked["shown"], grade=worked["grade"], grade_point=worked["point"], outcome=worked["outcome"],
        failed_components=worked["failed"], inputs=inputs, inputs_hash=digest, scheme_revision=scheme.revision,
        reason=reason, published_by=actor, published_at=now,
    )  # fmt: skip
    if candidate.registration_id:
        _to_attempt(actor, candidate, version)
    return version


def _to_attempt(actor, candidate: Candidate, result: ResultVersion) -> None:
    """S7-07: an offering's published result is the attempt's outcome."""
    attempt = CourseAttempt.objects.filter(registration_id=candidate.registration_id).first()
    if attempt is None:
        return
    graded = result.outcome in (ResultVersion.Outcome.PASSED, ResultVersion.Outcome.FAILED)
    attempt.outcome = result.outcome
    attempt.grade_point = result.grade_point if graded else None
    attempt.recorded_by, attempt.recorded_at = actor, timezone.now()
    attempt.save()


def publish(actor, a: Assessment, version: int) -> Assessment:
    _require(actor, a.institution, PUBLISH)
    with transaction.atomic():
        a = _locked(a, version)
        if a.state != State.MODERATED:
            raise Problem(409, "invalid_transition", "Marks are moderated before they are published.")
        candidates = list(a.candidates.prefetch_related("marks"))
        complete = {c.id: _marks_of(c, a.scheme) for c in candidates}
        if missing := [c for c in candidates if complete[c.id] is None]:
            raise Problem(409, "missing_marks", f"{len(missing)} student(s) still have missing marks.")
        for candidate in candidates:
            _record(actor, candidate, complete[candidate.id])
        a.state, a.published_by, a.published_at = State.PUBLISHED, actor, timezone.now()
        a.save()
        audit.log(
            actor, "results.published", a, f"{a.title}: {len(candidates)} results published", institution=a.institution
        )
        return a


# Revaluation (S7-08)


def open_case(actor, candidate: Candidate, reason: str, marks: dict) -> RevisionCase:
    a = candidate.assessment
    if not any(has_perm(actor, a.institution, p, WHOLE) for p in (MODERATE, PUBLISH)):
        raise PermissionDenied("Revaluations are raised by moderators or publishers.")
    if a.state != State.PUBLISHED:
        raise Problem(409, "invalid_transition", "Only published results are revalued.")
    components = {str(c.id) for c in a.scheme.components.all()}
    if not marks or set(marks) - components:
        raise ValidationError({"marks": ["Give the corrected marks for this assessment's components."]})
    return RevisionCase.objects.create(candidate=candidate, reason=reason, marks=marks, requested_by=actor)


def decide_case(actor, case: RevisionCase, approve: bool) -> RevisionCase:
    a = case.candidate.assessment
    _require(actor, a.institution, PUBLISH)
    if case.requested_by_id == actor.id:
        raise PermissionDenied("Someone other than who raised the revaluation approves it.")
    with transaction.atomic():
        case = RevisionCase.objects.select_for_update().select_related("candidate__assessment__scheme").get(pk=case.pk)
        if case.state != RevisionCase.State.REQUESTED:
            raise Problem(409, "invalid_transition", "This revaluation has been decided.")
        case.state = RevisionCase.State.APPROVED if approve else RevisionCase.State.REJECTED
        case.decided_by, case.decided_at = actor, timezone.now()
        case.save()
        if approve:
            current = case.candidate.results.filter(superseded_at__isnull=True).first()
            marks = {
                **{
                    k: {"status": v["status"], "score": Decimal(v["score"]) if v["score"] is not None else None}
                    for k, v in current.inputs["marks"].items()
                },
                **{
                    k: {"status": v["status"], "score": Decimal(v["score"]) if v.get("score") is not None else None}
                    for k, v in case.marks.items()
                },
            }
            ids = {str(c.id): c.id for c in case.candidate.assessment.scheme.components.all()}
            _record(actor, case.candidate, {ids[k]: v for k, v in marks.items()}, reason=case.reason)
            audit.log(actor, "results.revised", a, f"Revaluation approved: {case.reason}", institution=a.institution)
        return case


# Promotion, documents and verification (S7-09..11)


def decide_promotion(actor, enrollment: Enrollment, year, decision: str, reason: str) -> PromotionDecision:
    _require(actor, enrollment.institution, PUBLISH)
    made, _ = PromotionDecision.objects.update_or_create(
        enrollment=enrollment, year=year, defaults={"decision": decision, "reason": reason, "decided_by": actor}
    )
    return made


PREFIX = {"report_card": "RC", "transcript": "TR", "award": "AW"}


def _number(institution, kind: str) -> str:
    year = timezone.now().year
    prefix = f"{PREFIX[kind]}-{year}-"
    taken = IssuedDocument.objects.filter(institution=institution, number__startswith=prefix).values_list(
        "number", flat=True
    )
    return f"{prefix}{max((int(n[len(prefix) :]) for n in taken), default=0) + 1:05d}"


def _issue(
    actor, institution, kind: str, holder: str, title: str, content: dict, student=None, key=None
) -> IssuedDocument:
    """Number, hash and token a frozen document; the holder's previous current one of the same kind and key goes
    superseded."""
    from institutions.models import Institution

    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=institution.pk)  # numbers one at a time
        current = IssuedDocument.Status.CURRENT
        same = {"institution": institution, "kind": kind, "student": student, "holder_name": holder, "title": title}
        previous = IssuedDocument.objects.filter(status=current, **same).first()
        body = json.dumps(content, sort_keys=True, default=str)
        made = IssuedDocument.objects.create(
            institution=institution, kind=kind, student=student, holder_name=holder, number=_number(institution, kind),
            title=title, content=json.loads(body), content_hash=hashlib.sha256(body.encode()).hexdigest(),
            token=secrets.token_urlsafe(24), supersedes=previous, issued_by=actor,
        )  # fmt: skip
        if previous is not None:
            previous.status = IssuedDocument.Status.SUPERSEDED
            previous.save(update_fields=["status"])
        audit.log(
            actor,
            f"document.{kind}_issued",
            made,
            f"{made.get_kind_display()} {made.number} for {holder}",
            institution=institution,
        )
        return made


def _current_results(enrollment: Enrollment, **scope):
    return ResultVersion.objects.filter(
        candidate__enrollment=enrollment, superseded_at__isnull=True, **scope
    ).select_related(
        "candidate__assessment__subject", "candidate__assessment__offering__course", "candidate__assessment__term"
    )


def report_card(actor, student: Student, term: Term) -> IssuedDocument:
    _require(actor, student.institution, PUBLISH)
    enrollment = student.enrollments.filter(status="active").first() or student.enrollments.first()
    rows = _current_results(enrollment, candidate__assessment__term=term, candidate__assessment__section__isnull=False)
    promotion = PromotionDecision.objects.filter(enrollment=enrollment, year=term.year).first()
    content = {
        "student": {"number": student.number, "name": student.person.full_name},
        "term": f"{term.year.code} {term.name}",
        "subjects": [
            {
                "subject": r.candidate.assessment.subject.name,
                "assessment": r.candidate.assessment.title,
                "total": r.shown_total,
                "grade": r.grade,
                "outcome": r.outcome,
                "revision": r.revision,
            }
            for r in rows
        ],  # fmt: skip
        "attendance": {k: v for k, v in attendance.summary([enrollment]).items() if k != "absences"},
        "promotion": promotion.get_decision_display() if promotion else None,
    }
    title = f"Report card {term.year.code} {term.name}"
    return _issue(actor, student.institution, "report_card", student.person.full_name, title, content, student)


def transcript(actor, student: Student) -> IssuedDocument:
    from academics import progress as degree

    _require(actor, student.institution, PUBLISH)
    enrollment = student.enrollments.filter(status="active").first() or student.enrollments.first()
    shown = degree.progress(enrollment)
    content = {
        "student": {"number": student.number, "name": student.person.full_name},
        "program": shown["program"],
        "regulation": shown["regulation"],
        "attempts": shown["attempts"],
        "terms": shown["terms"],
        "cgpa": shown["cgpa"],
        "credits": {"earned": shown["credits"]["earned"], "accepted": shown["credits"]["accepted"]},
        "transfers": [
            {k: t[k] for k in ("source_institution", "source_course", "approved_credits", "decision")}
            for t in shown["transfers"]
        ],
    }
    return _issue(actor, student.institution, "transcript", student.person.full_name, "Transcript", content, student)


def award(actor, student: Student, exception: str = "") -> IssuedDocument:
    from academics import progress as degree

    _require(actor, student.institution, PUBLISH)
    enrollment = student.enrollments.filter(status="active").first() or student.enrollments.first()
    if enrollment is None or enrollment.program_id is None:
        raise ValidationError({"kind": ["An award needs a program."]})
    shown = degree.progress(enrollment)
    accepted, required = Decimal(shown["credits"]["accepted"]), Decimal(shown["credits"]["required"])
    if accepted < required and not exception.strip():
        raise ValidationError(
            {
                "exception": [
                    f"{accepted} of {required} credits accepted; give the authorised exception to issue anyway."
                ]
            }
        )
    program = enrollment.program
    content = {
        "student": {"number": student.number, "name": student.person.full_name},
        "qualification": program.qualification,
        "program": {"code": program.code, "name": program.name},
        "regulation": shown["regulation"],
        "cgpa": shown["cgpa"],
        "credits": shown["credits"]["accepted"],
        "exception": exception.strip(),
    }
    title = f"{program.qualification} — {program.name}"
    return _issue(actor, student.institution, "award", student.person.full_name, title, content, student)


def award_affiliated(actor, university, row) -> IssuedDocument:
    """A university's award to an affiliated college's student, from its current accepted record (S5E-04)."""
    _require(actor, university, PUBLISH)
    content = {
        "student": {"number": row.number, "name": row.full_name},
        "college": row.batch.grant.college.display_name,
        "program": row.program,
        "regulation": row.regulation,
        "record": {"batch": str(row.batch.reference), "revision": row.batch.revision, "attempts": row.attempts},
    }
    return _issue(
        actor,
        university,
        "award",
        row.full_name,
        f"Award — {row.program} ({row.batch.grant.college.display_name})",
        content,
    )


def revoke(actor, document: IssuedDocument, reason: str) -> IssuedDocument:
    _require(actor, document.institution, PUBLISH)
    if not reason.strip():
        raise ValidationError({"reason": ["Say why."]})
    document.status, document.reason = IssuedDocument.Status.REVOKED, reason.strip()
    document.save(update_fields=["status", "reason"])
    audit.log(
        actor, "document.revoked", document, f"{document.number} revoked: {reason}", institution=document.institution
    )
    return document


def verification(document: IssuedDocument) -> dict:
    """What anyone holding the link may see (S7-11): enough to check, nothing more."""
    parts = document.holder_name.split()
    holder = f"{parts[0][0]}. {parts[-1]}" if len(parts) > 1 else f"{document.holder_name[:1]}."
    later = getattr(document, "superseded_by", None) if document.status == IssuedDocument.Status.SUPERSEDED else None
    return {
        "institution": document.institution.display_name,
        "kind": document.get_kind_display(),
        "number": document.number,
        "issued_on": document.issued_at.date(),
        "holder": holder,
        "status": document.status,
        "superseded_by": later.number if later else None,
    }


# Outcomes (S7-12)


def add_outcome(actor, course, data: dict) -> CourseOutcome:
    _require(actor, course.institution, MANAGE)
    if CourseOutcome.objects.filter(course=course, code=data["code"]).exists():
        raise ValidationError({"code": ["This course already has that outcome."]})
    return CourseOutcome.objects.create(course=course, **data)


def map_outcome(actor, a: Assessment, component_id, outcome_id) -> OutcomeMapping:
    _require(actor, a.institution, MANAGE)
    component = a.scheme.components.filter(pk=component_id).first()
    outcome = CourseOutcome.objects.filter(pk=outcome_id, course=a.offering.course if a.offering_id else None).first()
    if component is None or outcome is None:
        raise ValidationError({"outcome": ["Choose a component of this scheme and an outcome of this course."]})
    made, _ = OutcomeMapping.objects.get_or_create(assessment=a, component=component, outcome=outcome)
    return made


def attainment(actor, a: Assessment, threshold: Decimal) -> AttainmentRun:
    """Share of candidates at or above the threshold on each outcome's mapped components, from published marks."""
    _require(actor, a.institution, MANAGE)
    if a.state != State.PUBLISHED:
        raise Problem(409, "invalid_transition", "Attainment is worked out from published results.")
    by_outcome: dict = {}
    for m in a.mappings.select_related("outcome", "component"):
        by_outcome.setdefault(m.outcome, []).append(m.component)
    found, inputs = [], {}
    for outcome, components in sorted(by_outcome.items(), key=lambda kv: kv[0].code):
        reached = counted = 0
        for candidate in a.candidates.all():
            current = candidate.results.filter(superseded_at__isnull=True).first()
            marks = current.inputs["marks"] if current else {}
            scored = [marks.get(str(c.id)) for c in components]
            if not all(s and s["status"] == "scored" for s in scored):
                continue  # absent or exempt: no evidence either way
            counted += 1
            got = sum(Decimal(s["score"]) for s in scored)
            out_of = sum((c.max_marks for c in components), Decimal(0))
            reached += got * HUNDRED / out_of >= threshold
            inputs[f"{outcome.code}:{candidate.id}"] = str(got)
        share = (Decimal(reached) * HUNDRED / counted).quantize(Decimal("0.1")) if counted else None
        found.append(
            {
                "outcome": outcome.code,
                "candidates": counted,
                "attained": reached,
                "percent": str(share) if share is not None else None,
            }
        )
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return AttainmentRun.objects.create(
        assessment=a, threshold_percent=threshold, results=found, inputs_hash=digest, run_by=actor
    )


# Items


def scheme_item(s: Scheme) -> dict:
    return {
        "id": str(s.id),
        "version": s.version,
        "name": s.name,
        "revision": s.revision,
        "status": s.status,
        "pass_percent": str(s.pass_percent),
        "decimals": s.decimals,
        "bands": s.bands,
        "components": [
            {
                "id": str(c.id),
                "name": c.name,
                "max_marks": str(c.max_marks),
                "weight": str(c.weight),
                "min_percent": str(c.min_percent) if c.min_percent is not None else None,
            }
            for c in s.components.all()
        ],  # fmt: skip
    }


def result_item(r: ResultVersion | None) -> dict | None:
    if r is None:
        return None
    return {
        "revision": r.revision,
        "total": r.shown_total or None,
        "grade": r.grade,
        "grade_point": str(r.grade_point) if r.grade_point is not None else None,
        "outcome": r.outcome,
        "failed_components": r.failed_components,
        "published_at": r.published_at,
        "reason": r.reason,
    }


def _last_run(a: Assessment) -> dict | None:
    run = a.attainment_runs.order_by("-run_at").first()
    return {"threshold_percent": str(run.threshold_percent), "results": run.results} if run else None


def assessment_item(a: Assessment, viewer=None) -> dict:
    target = _target(a)
    candidates = a.candidates.select_related("enrollment__student__person").prefetch_related("marks", "results")
    return {
        "id": str(a.id),
        "version": a.version,
        "title": a.title,
        "state": a.state,
        "state_label": a.get_state_display(),
        "returned_reason": a.returned_reason,
        "term": {"id": str(a.term_id), "name": a.term.name},
        "target": {
            "kind": "section" if a.section_id else "offering",
            "id": str(target.id),
            "label": attendance.label(target),
        },
        "subject": a.subject.name if a.subject_id else None,
        "course": {"id": str(a.offering.course_id), "code": a.offering.course.code} if a.offering_id else None,
        "scheme": scheme_item(a.scheme),
        "candidates": [
            {
                "id": str(c.id),
                "student": {
                    "id": str(c.enrollment.student_id),
                    "number": c.enrollment.student.number,
                    "full_name": c.enrollment.student.person.full_name,
                },
                "marks": {
                    str(m.component_id): {"status": m.status, "score": str(m.score) if m.score is not None else None}
                    for m in c.marks.all()
                },
                "result": result_item(next((r for r in c.results.all() if r.superseded_at is None), None)),
            }  # fmt: skip
            for c in sorted(candidates, key=lambda c: c.enrollment.student.number)
        ],
        "can_evaluate": can_evaluate(viewer, a) if viewer else False,
        "cases": [
            {
                "id": str(case.id),
                "student": case.candidate.enrollment.student.number,
                "reason": case.reason,
                "requested_by": case.requested_by.full_name,
            }
            for case in RevisionCase.objects.filter(
                candidate__assessment=a, state=RevisionCase.State.REQUESTED
            ).select_related("candidate__enrollment__student", "requested_by")
        ],  # fmt: skip
        "mappings": [
            {"component": str(m.component_id), "outcome": m.outcome.code} for m in a.mappings.select_related("outcome")
        ],
        "attainment": _last_run(a),
    }


def document_item(d: IssuedDocument) -> dict:
    return {
        "id": str(d.id),
        "kind": d.kind,
        "kind_label": d.get_kind_display(),
        "number": d.number,
        "title": d.title,
        "status": d.status,
        "reason": d.reason,
        "issued_at": d.issued_at,
        "token": d.token,
        "content": d.content,
        "content_hash": d.content_hash,
    }
