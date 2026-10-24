"""Student records for staff, and a student's own record (slice 4a spec §5)."""

from django.db import transaction
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Membership
from accounts.permissions import WHOLE, active_membership, grants, has_perm, today_for
from accounts.role_views import holds_any
from common import audit
from common.models import AuditEvent
from common.pagination import Pages
from configuration.gates import require_module
from configuration.serializers import VersionInput
from students import guardians, logins, pinning, withdrawal
from students.models import GuardianLink, Student
from students.serializers import (
    PinInput,
    ProposeInput,
    RevokeInput,
    StudentInput,
    VerifyInput,
    WithdrawInput,
    link_item,
    student_item,
    student_list_item,
)


def visible_students(actor, institution):
    """Every student for whole-institution readers; otherwise students currently enrolled at a covered campus."""
    scopes = [where for perms, where in grants(active_membership(actor, institution)) if "student.read" in perms]
    found = institution.students.select_related("person", "application", "user")
    if WHOLE in scopes:
        return found
    campuses = [pk for kind, pk in scopes if kind == "campus"]
    return found.filter(enrollments__status="active", enrollments__campus_id__in=campuses).distinct()


class StudentView(GenericAPIView):
    permission_classes = [holds_any("student.read")]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "students")

    def detail(self, student: Student) -> dict:
        """The record with what this viewer may do to it now."""
        allowed = has_perm(self.request.user, self.request.institution, "student.update", student.scope)
        return {
            **student_item(student),
            "can_withdraw": allowed and student.status == Student.Status.ACTIVE,
            "can_reinstate": allowed and withdrawal.can_reinstate(student),
            "can_change_program": allowed and student.status == Student.Status.ACTIVE,
            "can_manage_guardians": guardians.can_manage_links(self.request.user, student),
        }

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
        return Response(self.detail(self.student()))

    def patch(self, request, pk):
        found = self.student()
        if not has_perm(request.user, request.institution, "student.update", found.scope):
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
        return Response(self.detail(student))


class StudentProgram(StudentView):
    def post(self, request, pk):
        require_module(request.institution, "academics")
        data = PinInput(data=request.data)
        data.is_valid(raise_exception=True)
        student = pinning.pin(request.user, self.student(), **data.validated_data)
        return Response(self.detail(student))


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
        return Response(
            {
                key: item[key]
                for key in ("number", "full_name", "date_of_birth", "status", "enrollment", "current_section")
            }
        )


class GuardianView(StudentView):
    """A student's guardian links. Reading follows student.read; changing needs guardian_link.manage there."""

    def managed(self) -> Student:
        found = self.student()
        if not guardians.can_manage_links(self.request.user, found):
            raise PermissionDenied("Your role cannot change guardian links for this student.")
        return found

    def link(self, student: Student) -> GuardianLink:
        found = student.guardian_links.filter(pk=self.kwargs["link"]).first()
        if found is None:
            raise NotFound()
        return found

    def item(self, link: GuardianLink, student: Student) -> dict:
        full = guardians.can_manage_links(self.request.user, student)
        return link_item(link, full, today_for(student.institution))

    def body(self, serializer_class) -> dict:
        data = serializer_class(data=self.request.data)
        data.is_valid(raise_exception=True)
        return data.validated_data


class GuardianList(GuardianView):
    def get(self, request, pk):
        student = self.student()
        links = student.guardian_links.select_related("adult", "student__person")
        return Response([self.item(link, student) for link in links])

    def post(self, request, pk):
        student = self.managed()
        data = self.body(ProposeInput)
        with transaction.atomic():
            link = guardians.propose(request.user, student, data["adult"], data["relationship"])
        return Response(self.item(link, student), status=status.HTTP_201_CREATED)


class GuardianVerify(GuardianView):
    def post(self, request, pk, link):
        student = self.managed()
        link = self.link(student)  # the record first: an unknown id is 404 whatever the body says
        data = self.body(VerifyInput)
        found = guardians.verify(request.user, link, data.pop("version"), data)
        return Response(self.item(found, student))


class GuardianRevoke(GuardianView):
    def post(self, request, pk, link):
        student = self.managed()
        link = self.link(student)
        data = self.body(RevokeInput)
        found = guardians.revoke(request.user, link, data["version"], data["reason"])
        return Response(self.item(found, student))


class Withdraw(StudentView):
    def post(self, request, pk):
        found = self.student()
        data = WithdrawInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        student = withdrawal.withdraw(
            request.user, found, values["version"], values["effective_on"], values["reason"], values["clearance_note"]
        )
        return Response(self.detail(student))


class Reinstate(StudentView):
    def post(self, request, pk):
        found = self.student()
        data = VersionInput(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(self.detail(withdrawal.reinstate(request.user, found, data.validated_data["version"])))


class StudentHistory(StudentView):
    pagination_class = Pages

    def get(self, request, pk):
        student = self.student()
        events = AuditEvent.objects.filter(object_type="student", object_id=str(student.id)).select_related("actor")
        page = self.paginate_queryset(events.order_by("-at"))
        return self.get_paginated_response(
            [
                {
                    "at": event.at,
                    "actor": event.actor.full_name if event.actor_id else None,
                    "action": event.action,
                    "summary": event.summary,
                    "changes": event.changes,
                }
                for event in page
            ]
        )


class LoginInput(serializers.Serializer):
    version = serializers.IntegerField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class GiveLogin(StudentView):
    def post(self, request, pk):
        found = self.student()
        data = LoginInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        return Response(self.detail(logins.give_login(request.user, found, values["version"], values["password"])))
