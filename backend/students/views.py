"""Student records for staff, and a student's own record (slice 4a spec §5)."""

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Membership
from accounts.permissions import WHOLE, active_membership, grants, has_perm
from accounts.role_views import holds_any
from common import audit
from common.pagination import Pages
from configuration.gates import require_module
from students.models import Student
from students.serializers import StudentInput, student_item, student_list_item


def visible_students(actor, institution):
    """Every student for whole-institution readers; otherwise students currently enrolled at a covered campus."""
    scopes = [where for perms, where in grants(active_membership(actor, institution)) if "student.read" in perms]
    found = institution.students.select_related("person", "application", "user")
    if WHOLE in scopes:
        return found
    campuses = [pk for kind, pk in scopes if kind == "campus"]
    return found.filter(enrollments__status="active", enrollments__campus_id__in=campuses).distinct()


def _scope(student: Student):
    current = student.enrollments.filter(status="active").first()
    return ("campus", current.campus_id) if current and current.campus_id else WHOLE


class StudentView(GenericAPIView):
    permission_classes = [holds_any("student.read")]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "students")

    def student(self) -> Student:
        found = visible_students(self.request.user, self.request.institution).filter(pk=self.kwargs["pk"]).first()
        if found is None:
            raise NotFound()
        return found


class StudentList(StudentView):
    pagination_class = Pages

    def get(self, request):
        queryset = visible_students(request.user, request.institution)
        if len(search := request.query_params.get("search", "").strip()) >= 3:
            queryset = queryset.filter(Q(number__icontains=search) | Q(person__full_name__icontains=search))
        if state := request.query_params.get("status"):
            queryset = queryset.filter(status=state)
        page = self.paginate_queryset(queryset.order_by("number"))
        return self.get_paginated_response([student_list_item(student) for student in page])


class StudentDetail(StudentView):
    def get(self, request, pk):
        return Response(student_item(self.student()))

    def patch(self, request, pk):
        found = self.student()
        if not has_perm(request.user, request.institution, "student.update", _scope(found)):
            raise PermissionDenied("Your role cannot correct this student's details.")
        data = StudentInput(data=request.data)
        data.is_valid(raise_exception=True)
        changes = dict(data.validated_data)
        with transaction.atomic():
            student = Student.objects.select_for_update().select_related("person").get(pk=found.pk)
            student.check_version(changes.pop("version"))
            person = student.person
            diff = {
                name: {"from": str(getattr(person, name)), "to": str(value)}
                for name, value in changes.items()
                if getattr(person, name) != value
            }
            for name, value in changes.items():
                setattr(person, name, value)
            person.save()
            student.save()  # the record's version covers its details
            if diff:
                audit.log(
                    request.user, "student.updated", student, f"Corrected {student.number}'s details", changes=diff
                )
        return Response(student_item(student))


class OwnRecord(GenericAPIView):
    """A student's own record, for the student portal."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.site_kind != "institution":
            raise NotFound()
        membership = active_membership(request.user, request.institution)
        if membership is None or membership.kind != Membership.Kind.STUDENT:
            raise NotFound()
        require_module(request.institution, "students")
        student = request.institution.students.filter(user=request.user).select_related("person").first()
        if student is None:
            raise NotFound()
        item = student_item(student)
        return Response({key: item[key] for key in ("number", "full_name", "date_of_birth", "status", "enrollment")})
