from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView

from accounts.models import RoleAssignment
from accounts.permissions import live, today_for
from common import audit
from common.exceptions import Problem
from common.pagination import Pages
from institutions.models import Institution
from organization.models import Campus, Department
from organization.serializers import CampusSerializer, DepartmentSerializer
from sites.permissions import member_with


def in_use(detail: str) -> Problem:
    return Problem(409, "in_use", detail)


def live_assignments(institution, **scope):
    return live(RoleAssignment.objects.filter(**scope), today_for(institution))


class OrgView:
    """Every member may read the institution's campuses and departments; changing them needs organization.manage."""

    pagination_class = Pages
    model = None
    kind = ""

    def get_permissions(self):
        perm = "institution.read" if self.request.method == "GET" else "organization.manage"
        return [member_with(perm)()]

    def get_queryset(self):
        queryset = self.model.objects.filter(institution=self.request.institution)
        params = self.request.query_params
        if len(search := params.get("search", "").strip()) >= 3:
            queryset = queryset.filter(Q(code__icontains=search) | Q(name__icontains=search))
        if params.get("active") == "1":
            queryset = queryset.filter(is_active=True)
        return queryset


class OrgList(OrgView, ListCreateAPIView):
    def perform_create(self, serializer):
        serializer.validated_data.pop("version", None)
        record = serializer.save(institution=self.request.institution)
        audit.log(self.request.user, f"{self.kind}.created", record, f"Added {self.kind} {record.name}")


class OrgDetail(OrgView, RetrieveUpdateAPIView):
    http_method_names = ["get", "patch"]

    def perform_update(self, serializer):
        changes = dict(serializer.validated_data)
        version = changes.pop("version", None)
        with transaction.atomic():
            # One change to an institution's structure at a time, so two parent moves cannot together make a loop.
            Institution.objects.select_for_update().get(pk=self.request.institution.pk)
            record = self.model.objects.select_for_update().get(pk=serializer.instance.pk)
            record.check_version(version)
            self.check_locked(record, changes)
            if changes.get("is_active") is False and record.is_active:
                self.check_can_deactivate(record)
            diff = {
                name: {"from": _plain(getattr(record, name)), "to": _plain(value)}
                for name, value in changes.items()
                if getattr(record, name) != value
            }
            for name, value in changes.items():
                setattr(record, name, value)
            record.save()
            self.after_update(record, diff)
            if diff:
                summary = f"Changed {self.kind} {record.name}"
                audit.log(self.request.user, f"{self.kind}.updated", record, summary, changes=diff)
        serializer.instance = record

    def check_can_deactivate(self, record) -> None:
        raise NotImplementedError

    def check_locked(self, record, changes: dict) -> None:
        """Checks that need the current state, made again under the lock."""

    def after_update(self, record, diff: dict) -> None:
        pass


def _plain(value):
    return value.name if hasattr(value, "name") and hasattr(value, "pk") else value


class CampusList(OrgList):
    model, kind, serializer_class = Campus, "campus", CampusSerializer


class CampusDetail(OrgDetail):
    model, kind, serializer_class = Campus, "campus", CampusSerializer

    def check_can_deactivate(self, campus: Campus) -> None:
        institution = self.request.institution
        if campus.departments.filter(is_active=True).exists():
            raise in_use("Deactivate or move its departments first.")
        if (count := live_assignments(institution, campus=campus).count()) > 0:
            raise in_use(f"{count} {'person has a role' if count == 1 else 'people have roles'} at this campus.")
        if not institution.campuses.filter(is_active=True).exclude(pk=campus.pk).exists():
            raise in_use("An institution needs at least one active campus.")


class DepartmentList(OrgList):
    model, kind, serializer_class = Department, "department", DepartmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related("campus", "parent")
        if campus := self.request.query_params.get("campus"):
            queryset = queryset.filter(campus_id=campus)
        return queryset


class DepartmentDetail(OrgDetail):
    model, kind, serializer_class = Department, "department", DepartmentSerializer

    def check_can_deactivate(self, department: Department) -> None:
        if department.children.filter(is_active=True).exists():
            raise in_use("Deactivate its departments first.")
        if (count := live_assignments(self.request.institution, department=department).count()) > 0:
            raise in_use(f"{count} {'person has a role' if count == 1 else 'people have roles'} in this department.")

    def check_locked(self, department: Department, changes: dict) -> None:
        parent = changes.get("parent")
        if parent is not None and (parent.pk == department.pk or parent.pk in department.descendant_ids()):
            raise ValidationError({"parent": ["A department cannot sit under itself or one of its own departments."]})

    def after_update(self, department: Department, diff: dict) -> None:
        # Departments below follow their parent to a new campus.
        if "campus" in diff:
            Department.objects.filter(pk__in=department.descendant_ids()).update(campus=department.campus)
