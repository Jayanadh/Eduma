"""An applicant's own application: start, fill in, submit, withdraw, accept an offer (slice 4a spec §4). The applicant
never decides institution, owner, number, stage or outcome; those come from the server."""

import datetime as dt

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.permissions import today_for
from admissions.models import AdmissionCycle, Application, Document, Question, Submission
from common import audit
from common.exceptions import Problem

Stage = Application.Stage
EDITABLE = (Stage.DRAFT, Stage.NEEDS_INFORMATION)
WITHDRAWABLE = (
    Stage.DRAFT,
    Stage.SUBMITTED,
    Stage.UNDER_REVIEW,
    Stage.NEEDS_INFORMATION,
    Stage.ELIGIBLE,
    Stage.OFFERED,
    Stage.OFFER_EXPIRED,
)
CORE = (
    "learner_name",
    "date_of_birth",
    "guardian_name",
    "guardian_relationship",
    "guardian_phone",
    "guardian_email",
    "address",
    "previous_school",
)
# What the family is told when a required core field is empty, so the list says which one.
REQUIRED_CORE = {
    "learner_name": "Enter the learner's full name.",
    "date_of_birth": "Enter the learner's date of birth.",
    "guardian_name": "Enter the parent or guardian's name.",
    "guardian_relationship": "Say how the parent or guardian is related to the learner.",
    "guardian_phone": "Enter the parent or guardian's phone number.",
    "address": "Enter the family's address.",
}
LIVE_DOCUMENTS = (Document.Status.PENDING, Document.Status.VERIFIED)


def wrong_stage(application: Application) -> Problem:
    return Problem(409, "invalid_transition", f"This application is {application.get_stage_display().lower()}.")


def _closed(cycle: AdmissionCycle) -> Problem:
    return Problem(409, "admissions_closed", f"Applications for {cycle.name} are not being taken now.")


def is_open(cycle: AdmissionCycle) -> bool:
    today = today_for(cycle.institution)
    return cycle.status == AdmissionCycle.Status.PUBLISHED and cycle.opens_on <= today <= cycle.closes_on


def expire_if_due(application: Application) -> Application:
    """An offer past its expiry date stops holding a seat; stored the first time anything looks at it."""
    if (
        application.stage == Stage.OFFERED
        and application.offer_expires_on is not None
        and application.offer_expires_on < today_for(application.institution)
    ):
        Application.objects.filter(pk=application.pk, stage=Stage.OFFERED).update(stage=Stage.OFFER_EXPIRED)
        application.refresh_from_db()
    return application


def _locked(application: Application) -> Application:
    return Application.objects.select_for_update().select_related("cycle", "institution").get(pk=application.pk)


def check_answer(question: Question, value):
    """The value, cleaned, or a ValidationError message for answers.<code>."""
    if value in (None, ""):
        return None
    kind = question.kind
    if kind == Question.Kind.YES_NO:
        if not isinstance(value, bool):
            raise ValueError("Choose yes or no.")
        return value
    if not isinstance(value, str):
        raise ValueError("Answer in words.")
    value = value.strip()
    if kind == Question.Kind.TEXT and len(value) > 500 or kind == Question.Kind.LONG_TEXT and len(value) > 2000:
        raise ValueError("This answer is too long.")
    if kind == Question.Kind.CHOICE and value not in question.options:
        raise ValueError("Choose one of the options.")
    if kind == Question.Kind.DATE:
        try:
            dt.date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("Enter a date such as 2020-05-17.") from error
    return value


def start(owner, institution, cycle_id, place_id, key=None) -> Application:
    if key is not None:
        existing = Application.objects.filter(creation_key=key, owner=owner, institution=institution).first()
        if existing is not None:
            return existing
    cycle = institution.cycles.filter(pk=cycle_id, status=AdmissionCycle.Status.PUBLISHED).first()
    if cycle is None:
        raise ValidationError({"cycle": ["Choose one of the open admission cycles."]})
    place = cycle.places.filter(pk=place_id).first()
    if place is None:
        raise ValidationError({"place": ["Choose one of this cycle's places."]})
    if not is_open(cycle):
        raise _closed(cycle)
    try:
        with transaction.atomic():
            return Application.objects.create(
                institution=institution, cycle=cycle, place=place, owner=owner, creation_key=key
            )
    except IntegrityError:
        # Two identical starts at once: the second finds the first.
        found = Application.objects.filter(creation_key=key, owner=owner).first()
        if found is None:
            raise
        return found


def edit(owner, application: Application, version: int, data: dict) -> Application:
    with transaction.atomic():
        application = _locked(application)
        application.check_version(version)
        if application.stage not in EDITABLE:
            raise wrong_stage(application)
        for name in CORE:
            if name in data:
                setattr(application, name, data[name])
        if "answers" in data:
            questions = {q.code: q for q in application.cycle.questions.all()}
            errors, answers = {}, dict(application.answers)
            for code, value in data["answers"].items():
                if code not in questions:
                    errors[f"answers.{code}"] = ["There is no such question."]
                    continue
                try:
                    answers[code] = check_answer(questions[code], value)
                except ValueError as error:
                    errors[f"answers.{code}"] = [str(error)]
            if errors:
                raise ValidationError(errors)
            application.answers = answers
        application.save()
        return application


def missing(application: Application) -> dict[str, list[str]]:
    """What still stops the application being submitted, by field."""
    errors = {name: [message] for name, message in REQUIRED_CORE.items() if not getattr(application, name)}
    for question in application.cycle.questions.all():
        if question.required and application.answers.get(question.code) in (None, ""):
            errors[f"answers.{question.code}"] = [f"Answer “{question.label}”."]
    present = set(application.documents.filter(status__in=LIVE_DOCUMENTS).values_list("requirement__code", flat=True))
    for requirement in application.cycle.documents.all():
        if requirement.required and requirement.code not in present:
            errors[f"documents.{requirement.code}"] = [f"Upload the {requirement.label.lower()}."]
    return errors


def snapshot(application: Application) -> dict:
    return {
        **{name: str(getattr(application, name) or "") for name in CORE},
        "place": application.place.label,
        "answers": application.answers,
        "documents": [
            {"code": doc.requirement.code, "name": doc.original_name, "status": doc.status}
            for doc in application.documents.filter(status__in=LIVE_DOCUMENTS).select_related("requirement")
        ],
    }


def _number(application: Application) -> str:
    cycle = AdmissionCycle.objects.select_for_update().get(pk=application.cycle_id)
    prefix = f"A{cycle.entry_year}-"
    taken = cycle.applications.filter(number__startswith=prefix).values_list("number", flat=True)
    return f"{prefix}{max((int(n[len(prefix) :]) for n in taken), default=0) + 1:04d}"


def submit(owner, application: Application, version: int) -> Application:
    with transaction.atomic():
        application = _locked(application)
        application.check_version(version)
        if application.stage not in EDITABLE:
            raise wrong_stage(application)
        # The dates bound new applications; a family answering a request for information may reply after them.
        if application.stage == Stage.DRAFT and not is_open(application.cycle):
            raise _closed(application.cycle)
        if errors := missing(application):
            raise ValidationError(errors)
        if not application.number:
            application.number = _number(application)
        application.revision += 1
        application.stage = Stage.SUBMITTED
        application.information_request = ""
        application.submitted_at = timezone.now()
        application.save()
        Submission.objects.create(
            application=application, revision=application.revision, snapshot=snapshot(application), submitted_by=owner
        )
        audit.log(
            owner,
            "application.submitted",
            application,
            f"{application.number} submitted for {application.learner_name}",
            institution=application.institution,
            changes={"revision": application.revision},
        )
        return application


def withdraw(owner, application: Application, version: int) -> Application:
    with transaction.atomic():
        application = _locked(application)
        application.check_version(version)
        if application.stage not in WITHDRAWABLE:
            raise wrong_stage(application)
        application.stage = Stage.WITHDRAWN
        application.save()
        audit.log(
            owner, "application.withdrawn", application, f"{application} withdrawn", institution=application.institution
        )
        return application


def accept(owner, application: Application, version: int) -> Application:
    expire_if_due(application)
    with transaction.atomic():
        application = _locked(application)
        application.check_version(version)
        if application.stage == Stage.OFFER_EXPIRED:
            raise Problem(409, "invalid_transition", f"This offer expired on {application.offer_expires_on}.")
        if application.stage != Stage.OFFERED:
            raise wrong_stage(application)
        application.stage = Stage.ACCEPTED
        application.save()
        audit.log(
            owner,
            "application.accepted",
            application,
            f"{application} offer accepted",
            institution=application.institution,
        )
        return application
