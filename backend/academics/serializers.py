from rest_framework import serializers

from academics.models import AcademicYear


class YearInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    status = serializers.ChoiceField(AcademicYear.Status.choices, required=False)


class YearPatch(YearInput):
    version = serializers.IntegerField()
    code = serializers.CharField(max_length=20, required=False)
    starts_on = serializers.DateField(required=False)
    ends_on = serializers.DateField(required=False)


class TermInput(serializers.Serializer):
    name = serializers.CharField(max_length=40)
    ordinal = serializers.IntegerField(min_value=1, max_value=12)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()


class TermPatch(TermInput):
    name = serializers.CharField(max_length=40, required=False)
    ordinal = serializers.IntegerField(min_value=1, max_value=12, required=False)
    starts_on = serializers.DateField(required=False)
    ends_on = serializers.DateField(required=False)


class GradeInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=60)
    order = serializers.IntegerField(min_value=0, max_value=1000, required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)


class SubjectInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=80)
    is_active = serializers.BooleanField(required=False, default=True)


class GradePatch(GradeInput):
    version = serializers.IntegerField()
    code = serializers.CharField(max_length=20, required=False)
    name = serializers.CharField(max_length=60, required=False)
    order = serializers.IntegerField(min_value=0, max_value=1000, required=False)
    is_active = serializers.BooleanField(required=False)


class SubjectPatch(SubjectInput):
    version = serializers.IntegerField()
    code = serializers.CharField(max_length=20, required=False)
    name = serializers.CharField(max_length=80, required=False)
    is_active = serializers.BooleanField(required=False)


def term_item(term) -> dict:
    return {
        "id": str(term.id),
        "name": term.name,
        "ordinal": term.ordinal,
        "starts_on": term.starts_on,
        "ends_on": term.ends_on,
    }


def year_item(year) -> dict:
    return {
        "id": str(year.id),
        "version": year.version,
        "code": year.code,
        "starts_on": year.starts_on,
        "ends_on": year.ends_on,
        "status": year.status,
        "status_label": year.get_status_display(),
        "terms": [term_item(term) for term in year.terms.all()],
    }


def named_item(row) -> dict:
    item = {"id": str(row.id), "version": row.version, "code": row.code, "name": row.name, "is_active": row.is_active}
    if hasattr(row, "order"):
        item["order"] = row.order
    return item
