"""Registration for staff (institution/academics/) and for students themselves (student/) — slice 5c §4."""

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics import progress, registration
from academics.models import (
    CourseAttempt,
    CourseOffering,
    CourseRegistration,
    CreditTransfer,
    CurriculumCourse,
    Hold,
    RegistrationOverride,
    RegistrationWindow,
)
from academics.serializers import (
    DecideTransferInput,
    HoldInput,
    OutcomeInput,
    OverrideInput,
    OwnRegisterInput,
    RegisterInput,
    TransferInput,
    VersionInput,
    WindowInput,
    WindowPatch,
)
from academics.views import AcademicsView, valid
from accounts.models import Membership
from accounts.permissions import active_membership, today_for
from accounts.role_views import holds_any
from common.pagination import Pages
from configuration.gates import require_module
from students.models import Student


class RegistrationView(AcademicsView):
    def get_permissions(self):
        return [holds_any("institution.read" if self.request.method == "GET" else registration.MANAGE)()]

    def student(self, pk) -> Student:
        return self.found(self.request.institution.students.select_related("person"), pk)


class WindowList(RegistrationView):
    def get(self, request):
        rows = RegistrationWindow.objects.filter(institution=request.institution).select_related("term__year")
        return Response([registration.window_item(w) for w in rows.order_by("-term__starts_on")])

    def post(self, request):
        window = registration.save_window(request.user, request.institution, None, valid(WindowInput, request.data))
        return Response(registration.window_item(window), status=status.HTTP_201_CREATED)


class WindowDetail(RegistrationView):
    def patch(self, request, pk):
        found = self.found(RegistrationWindow.objects.filter(institution=request.institution), pk)
        data = valid(WindowPatch, request.data)
        window = registration.save_window(request.user, request.institution, found, data, data.pop("version"))
        return Response(registration.window_item(window))


def _registrations(institution):
    return CourseRegistration.objects.filter(institution=institution).select_related(
        "offering__course", "offering__term", "enrollment__student__person", "curriculum"
    )


class RegistrationList(RegistrationView):
    pagination_class = Pages

    def get_permissions(self):
        perm = "student.read" if self.request.method == "GET" else registration.MANAGE
        return [holds_any(perm, registration.MANAGE)()]

    def get(self, request):
        rows = _registrations(request.institution)
        for name, field in (("offering", "offering_id"), ("student", "enrollment__student_id"), ("state", "state")):
            if value := request.query_params.get(name):
                rows = rows.filter(**{field: value})
        page = self.paginate_queryset(rows.order_by("-created_at"))
        return self.get_paginated_response([registration.registration_item(r) for r in page])

    def post(self, request):
        data = valid(RegisterInput, request.data)
        student = self.student(data["student"])
        registration._require(request.user, student)
        made, new = registration.register(request.user, student, data["offerings"], data["waitlist"])
        code = status.HTTP_201_CREATED if new else status.HTTP_200_OK
        return Response([registration.registration_item(r) for r in made], status=code)


class RegistrationAction(RegistrationView):
    action = staticmethod(registration.approve)

    def post(self, request, pk):
        found = self.found(_registrations(request.institution), pk)
        changed = self.action(request.user, found, valid(VersionInput, request.data)["version"])
        return Response(registration.registration_item(changed))


class HoldList(RegistrationView):
    def get(self, request, pk):
        student = self.student(pk)
        return Response([registration.hold_item(h) for h in student.holds.select_related("placed_by")])

    def post(self, request, pk):
        hold = registration.place_hold(request.user, self.student(pk), valid(HoldInput, request.data))
        return Response(registration.hold_item(hold), status=status.HTTP_201_CREATED)


class LiftHold(RegistrationView):
    def post(self, request, pk):
        hold = self.found(
            Hold.objects.filter(institution=request.institution).select_related("student", "placed_by"), pk
        )
        return Response(registration.hold_item(registration.lift_hold(request.user, hold)))


class OverrideList(RegistrationView):
    def get_permissions(self):
        perm = "student.read" if self.request.method == "GET" else registration.OVERRIDE
        return [holds_any(perm)()]

    def get(self, request):
        rows = RegistrationOverride.objects.filter(institution=request.institution).select_related(
            "offering__course", "granted_by", "curriculum"
        )
        if student := request.query_params.get("student"):
            rows = rows.filter(student_id=student)
        return Response([registration.override_item(o) for o in rows])

    def post(self, request):
        data = valid(OverrideInput, request.data)
        student = self.student(data.pop("student"))
        offering = self.found(CourseOffering.objects.filter(institution=request.institution), data.pop("offering"))
        made = registration.grant_override(request.user, student, offering, data)
        return Response(registration.override_item(made), status=status.HTTP_201_CREATED)


class OwnView(GenericAPIView):
    """A student's own registration, on their institution's host."""

    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        membership = (
            active_membership(request.user, request.institution) if request.site_kind == "institution" else None
        )
        if membership is None or membership.kind != Membership.Kind.STUDENT:
            raise NotFound()
        require_module(request.institution, "academics")
        self.me = request.institution.students.filter(user=request.user).select_related("person").first()
        if self.me is None:
            raise NotFound()


class OwnRegistration(OwnView):
    def get(self, request):
        today = today_for(request.institution)
        windows = RegistrationWindow.objects.filter(institution=request.institution, closes_on__gte=today)
        window = windows.select_related("term__year").order_by("opens_on").first()
        mine = _registrations(request.institution).filter(enrollment__student=self.me).order_by("-created_at")
        offerings = []
        if window is not None:
            pinned = self.me.enrollments.filter(status="active").values_list("curriculum_id", flat=True).first()
            in_regulation = CurriculumCourse.objects.filter(curriculum_id=pinned).values("course_id")
            rows = CourseOffering.objects.filter(
                term=window.term, status=CourseOffering.Status.OPEN, course_id__in=in_regulation
            )
            for offering in rows.select_related("course", "linked_to__course").prefetch_related("linked").distinct():
                seated = offering.registrations.filter(state__in=CourseRegistration.SEATED).count()
                offerings.append(
                    {
                        "id": str(offering.id),
                        "label": registration.label(offering),
                        "title": offering.course.title,
                        "credits": str(offering.course.credits),
                        "seats_left": max(offering.capacity - seated, 0),
                        "linked_to": str(offering.linked_to_id) if offering.linked_to_id else None,
                        "labs": [str(lab.id) for lab in registration._labs(offering)],
                        "problems": registration.problems(self.me, offering),
                    }
                )
        return Response(
            {
                "window": registration.window_item(window) if window else None,
                "offerings": sorted(offerings, key=lambda o: o["label"]),
                "registrations": [registration.registration_item(r) for r in mine],
            }
        )

    def post(self, request):
        data = valid(OwnRegisterInput, request.data)
        made, new = registration.register(request.user, self.me, data["offerings"], data["waitlist"])
        code = status.HTTP_201_CREATED if new else status.HTTP_200_OK
        return Response([registration.registration_item(r) for r in made], status=code)


class OwnDrop(OwnView):
    def post(self, request, pk):
        found = _registrations(request.institution).filter(enrollment__student=self.me, pk=pk).first()
        if found is None:
            raise NotFound()
        version = valid(VersionInput, request.data)["version"]
        return Response(
            registration.registration_item(registration.drop(request.user, found, version, by_student=True))
        )


class RecordView(RegistrationView):
    """Attempts, transfer credit and progress: read with student.read where the student is visible; changed with
    academic_record.manage."""

    def get_permissions(self):
        return [holds_any("student.read" if self.request.method == "GET" else progress.RECORD)()]

    def visible(self, pk) -> Student:
        from students.views import visible_students

        return self.found(visible_students(self.request.user, self.request.institution), pk)


class AttemptList(RecordView):
    def get(self, request):
        student = self.visible(request.query_params.get("student"))
        rows = CourseAttempt.objects.filter(enrollment__student=student).select_related("course", "term__year")
        return Response([progress.attempt_item(a) for a in rows])


class AttemptDetail(RecordView):
    def patch(self, request, pk):
        rows = CourseAttempt.objects.filter(institution=request.institution).select_related("course", "term__year")
        found = self.found(rows.select_related("enrollment__student"), pk)
        return Response(
            progress.attempt_item(progress.record_outcome(request.user, found, valid(OutcomeInput, request.data)))
        )


class TransferList(RecordView):
    def get(self, request):
        student = self.visible(request.query_params.get("student"))
        rows = CreditTransfer.objects.filter(enrollment__student=student).select_related("course")
        return Response([progress.transfer_item(t) for t in rows])

    def post(self, request):
        data = valid(TransferInput, request.data)
        student = self.student(data.pop("student"))
        enrollment = student.enrollments.filter(status="active").first() or student.enrollments.first()
        if enrollment is None:
            raise NotFound()
        made = progress.add_transfer(request.user, student, enrollment, data)
        return Response(progress.transfer_item(made), status=status.HTTP_201_CREATED)


class DecideTransfer(RecordView):
    def post(self, request, pk):
        rows = CreditTransfer.objects.filter(institution=request.institution).select_related(
            "enrollment__student", "course"
        )
        found = self.found(rows, pk)
        decided = progress.decide_transfer(request.user, found, valid(DecideTransferInput, request.data))
        return Response(progress.transfer_item(decided))


def _progress_of(student: Student) -> dict:
    enrollment = student.enrollments.filter(status="active").first() or student.enrollments.first()
    if enrollment is None:
        raise NotFound()
    return progress.progress(enrollment)


class StudentProgress(RecordView):
    def get(self, request, pk):
        return Response(_progress_of(self.visible(pk)))


class OwnProgress(OwnView):
    def get(self, request):
        return Response(_progress_of(self.me))
