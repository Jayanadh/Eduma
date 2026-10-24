"""Setting up admission cycles (slice 4a spec §2 S4-03): drafts are freely edited, publishing freezes them, closing
stops new applications."""

import datetime as dt

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from accounts.permissions import today_for
from admissions.models import AdmissionCycle, DocumentRequirement, Place, Question
from common import audit
from common.exceptions import Problem
from configuration.registry import academic_year, setting
from institutions.serializers import django_errors
from organization.models import validate_code


def _code(value: str) -> str:
    return django_errors(validate_code, value)


class PlaceInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    label = serializers.CharField(max_length=80)
    campus = serializers.UUIDField(allow_null=True, required=False, default=None)
    seats = serializers.IntegerField(min_value=1, max_value=10000)
    program = serializers.UUIDField(allow_null=True, required=False, default=None)

    def validate_code(self, value):
        return _code(value)

    def validate_program(self, value):
        if value is None:
            return None
        program = self.context["institution"].programs.filter(pk=value, is_active=True).first()
        if program is None:
            raise serializers.ValidationError("Choose one of the institution's active programs.")
        return program

    def validate_campus(self, value):
        if value is None:
            return None
        campus = self.context["institution"].campuses.filter(pk=value, is_active=True).first()
        if campus is None:
            raise serializers.ValidationError("Choose one of the institution's active campuses.")
        return campus


class QuestionInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    label = serializers.CharField(max_length=200)
    help = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    kind = serializers.ChoiceField(Question.Kind.choices)
    options = serializers.ListField(child=serializers.CharField(max_length=80), required=False, default=list)
    required = serializers.BooleanField(default=True)

    def validate_code(self, value):
        return _code(value)

    def validate(self, attrs):
        if attrs["kind"] == Question.Kind.CHOICE and len(set(attrs["options"])) < 2:
            raise serializers.ValidationError({"options": ["Give at least two different options."]})
        if attrs["kind"] != Question.Kind.CHOICE:
            attrs["options"] = []
        return attrs


class DocumentInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    label = serializers.CharField(max_length=120)
    help = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    required = serializers.BooleanField(default=True)

    def validate_code(self, value):
        return _code(value)


def _unique_codes(items, field: str):
    codes = [item["code"] for item in items]
    if len(codes) != len(set(codes)):
        raise serializers.ValidationError({field: ["Each code can be used once."]})


class CycleInput(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    entry_year = serializers.IntegerField(min_value=2000, max_value=2100)
    opens_on = serializers.DateField()
    closes_on = serializers.DateField()
    instructions = serializers.CharField(max_length=2000, allow_blank=True, required=False, default="")
    places = PlaceInput(many=True)
    questions = QuestionInput(many=True, required=False, default=list)
    documents = DocumentInput(many=True, required=False, default=list)
    version = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if attrs["closes_on"] < attrs["opens_on"]:
            raise serializers.ValidationError({"closes_on": ["Close on or after the opening day."]})
        _unique_codes(attrs["places"], "places")
        _unique_codes(attrs["questions"], "questions")
        _unique_codes(attrs["documents"], "documents")
        return attrs


def _write_lists(cycle: AdmissionCycle, data: dict) -> None:
    cycle.places.all().delete()
    cycle.questions.all().delete()
    cycle.documents.all().delete()
    Place.objects.bulk_create(Place(cycle=cycle, order=i, **item) for i, item in enumerate(data["places"]))
    Question.objects.bulk_create(Question(cycle=cycle, order=i, **item) for i, item in enumerate(data["questions"]))
    DocumentRequirement.objects.bulk_create(
        DocumentRequirement(cycle=cycle, order=i, **item) for i, item in enumerate(data["documents"])
    )


def _fields(institution, data: dict) -> dict:
    month = setting(institution, "academic.year_start")
    label, _, _ = academic_year(month, dt.date(data["entry_year"], month, 1))
    return {
        "name": data["name"],
        "entry_year": data["entry_year"],
        "academic_year": label,
        "opens_on": data["opens_on"],
        "closes_on": data["closes_on"],
        "instructions": data["instructions"],
    }


def save_cycle(institution, actor, cycle: AdmissionCycle | None, data: dict) -> AdmissionCycle:
    with transaction.atomic():
        if cycle is None:
            fields = _fields(institution, data)
            cycle = AdmissionCycle.objects.create(institution=institution, created_by=actor, **fields)
            action, verb = "admission_cycle.created", "Created"
        else:
            cycle = AdmissionCycle.objects.select_for_update().get(pk=cycle.pk)
            cycle.check_version(data.get("version"))
            if cycle.status != AdmissionCycle.Status.DRAFT:
                detail = "A published cycle cannot be changed. Close it and start another."
                raise Problem(409, "invalid_transition", detail)
            for name, value in _fields(institution, data).items():
                setattr(cycle, name, value)
            cycle.save()
            action, verb = "admission_cycle.updated", "Changed"
        _write_lists(cycle, data)
        audit.log(actor, action, cycle, f"{verb} {cycle.name}")
        return cycle


def _move(actor, cycle: AdmissionCycle, version: int, start: str, to: str, verb: str) -> AdmissionCycle:
    with transaction.atomic():
        cycle = AdmissionCycle.objects.select_for_update().get(pk=cycle.pk)
        cycle.check_version(version)
        if cycle.status != start:
            raise Problem(409, "invalid_transition", f"This cycle is {cycle.get_status_display().lower()}.")
        if to == AdmissionCycle.Status.PUBLISHED:
            if not cycle.places.exists():
                raise ValidationError({"places": ["Add at least one place before opening the cycle."]})
            if cycle.closes_on < today_for(cycle.institution):
                raise ValidationError({"closes_on": ["This cycle's closing day has passed."]})
        cycle.status = to
        cycle.save()
        audit.log(actor, f"admission_cycle.{to}", cycle, f"{verb} {cycle.name}")
        return cycle


def publish(actor, cycle, version):
    return _move(actor, cycle, version, AdmissionCycle.Status.DRAFT, AdmissionCycle.Status.PUBLISHED, "Opened")


def close(actor, cycle, version):
    return _move(actor, cycle, version, AdmissionCycle.Status.PUBLISHED, AdmissionCycle.Status.CLOSED, "Closed")
