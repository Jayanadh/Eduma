"""Shapes for applicants and for staff, kept apart: an applicant's payload never carries internal notes, reviewers,
review notes on accepted documents, or anything about other applicants (slice 4a spec §4)."""

from rest_framework import serializers

from admissions.applications import CORE, EDITABLE, LIVE_DOCUMENTS, WITHDRAWABLE, Stage, missing
from admissions.models import Application, Document


class StartInput(serializers.Serializer):
    cycle = serializers.UUIDField()
    place = serializers.UUIDField()


class ApplicationInput(serializers.Serializer):
    """What an applicant may change. Anything else in the request (stage, owner, number…) is ignored."""

    version = serializers.IntegerField()
    learner_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    date_of_birth = serializers.DateField(allow_null=True, required=False)
    guardian_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    guardian_relationship = serializers.CharField(max_length=40, allow_blank=True, required=False)
    guardian_phone = serializers.CharField(max_length=30, allow_blank=True, required=False)
    guardian_email = serializers.EmailField(allow_blank=True, required=False)
    address = serializers.CharField(max_length=500, allow_blank=True, required=False)
    previous_school = serializers.CharField(max_length=200, allow_blank=True, required=False)
    answers = serializers.DictField(required=False)

    def validate_date_of_birth(self, value):
        from accounts.permissions import today_for

        if value is not None and value > today_for(self.context["institution"]):
            raise serializers.ValidationError("A date of birth cannot be in the future.")
        return value


def document_item(document: Document, for_staff: bool) -> dict:
    item = {
        "id": str(document.id),
        "requirement": document.requirement.code,
        "label": document.requirement.label,
        "original_name": document.original_name,
        "content_type": document.content_type,
        "size": document.size,
        "status": document.status,
        "uploaded_at": document.created_at,
    }
    # An applicant sees why a document needs replacing, and nothing else of the review.
    if for_staff or document.status == Document.Status.REJECTED:
        item["review_note"] = document.review_note
    return item


def _cycle(application: Application) -> dict:
    cycle, place = application.cycle, application.place
    return {
        "cycle": {
            "id": str(cycle.id),
            "name": cycle.name,
            "academic_year": cycle.academic_year,
            "closes_on": cycle.closes_on,
        },
        "place": {
            "id": str(place.id),
            "label": place.label,
            "campus_name": place.campus.name if place.campus_id else None,
        },
        "questions": list(cycle.questions.values("code", "label", "help", "kind", "options", "required")),
        "requirements": list(cycle.documents.values("code", "label", "help", "required")),
    }


def applicant_item(application: Application) -> dict:
    stage = application.stage
    actions = []
    if stage in EDITABLE:
        actions += ["edit", "upload", "submit"]
    if stage in WITHDRAWABLE:
        actions.append("withdraw")
    if stage == Stage.OFFERED:
        actions.append("accept")
    documents = application.documents.filter(status__in=(*LIVE_DOCUMENTS, Document.Status.REJECTED))
    return {
        "id": str(application.id),
        "number": application.number,
        "stage": stage,
        "stage_label": application.get_stage_display(),
        "version": application.version,
        **_cycle(application),
        **{name: getattr(application, name) for name in CORE},
        "answers": application.answers,
        "information_request": application.information_request if stage == Stage.NEEDS_INFORMATION else "",
        "decision_reason": application.decision_reason if stage == Stage.REJECTED else "",
        "offer_expires_on": application.offer_expires_on if stage in (Stage.OFFERED, Stage.OFFER_EXPIRED) else None,
        "submitted_at": application.submitted_at,
        "documents": [document_item(doc, False) for doc in documents.select_related("requirement")],
        "missing": {field: messages[0] for field, messages in missing(application).items()}
        if stage in EDITABLE
        else {},
        "allowed_actions": actions,
    }
