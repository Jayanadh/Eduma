from rest_framework import serializers

from institutions.serializers import django_errors
from organization.models import Campus, Department, validate_code


class CodeMixin:
    def validate_code(self, value: str) -> str:
        code = django_errors(validate_code, value)
        clash = self.Meta.model.objects.filter(institution=self.context["request"].institution, code=code)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("This code is already used.")
        return code


class CampusSerializer(CodeMixin, serializers.ModelSerializer):
    version = serializers.IntegerField(required=False)

    class Meta:
        model = Campus
        fields = ["id", "code", "name", "address", "is_active", "version"]
        extra_kwargs = {"code": {"validators": []}}


def _named(record) -> dict | None:
    return {"id": record.id, "name": record.name} if record is not None else None


class DepartmentSerializer(CodeMixin, serializers.ModelSerializer):
    """`campus` and `parent` go in as ids and come out as {id, name}. With a parent, the campus is the parent's."""

    campus = serializers.UUIDField(required=False, allow_null=True)
    parent = serializers.UUIDField(required=False, allow_null=True)
    version = serializers.IntegerField(required=False)

    class Meta:
        model = Department
        fields = ["id", "code", "name", "campus", "parent", "is_active", "version"]
        extra_kwargs = {"code": {"validators": []}}

    def _institution(self):
        return self.context["request"].institution

    def validate_campus(self, value) -> Campus | None:
        if value is None:
            return None
        campus = self._institution().campuses.filter(pk=value).first()
        if campus is None:
            raise serializers.ValidationError("Choose one of this institution's campuses.")
        return campus

    def validate_parent(self, value) -> Department | None:
        if value is None:
            return None
        parent = self._institution().departments.filter(pk=value).first()
        if parent is None:
            raise serializers.ValidationError("Choose one of this institution's departments.")
        if self.instance is not None and (parent.pk == self.instance.pk or parent.pk in self.instance.descendant_ids()):
            raise serializers.ValidationError("A department cannot sit under itself or one of its own departments.")
        return parent

    def validate(self, attrs):
        parent = attrs["parent"] if "parent" in attrs else getattr(self.instance, "parent", None)
        if parent is not None:
            attrs["campus"] = parent.campus
        return attrs

    def to_representation(self, department: Department) -> dict:
        body = super().to_representation(department)
        body["campus"] = _named(department.campus)
        body["parent"] = _named(department.parent)
        return body
