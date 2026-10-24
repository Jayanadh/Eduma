"""Attendance and assignments: teachers (teaching/), managers (institution/attendance/), students (student/) and
guardians (family/) — slice 6."""

from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.models import CourseOffering, Section, TimetableSlot
from academics.registration_views import OwnView
from academics.teaching import TeachingView
from academics.views import valid
from accounts.role_views import holds_any
from attendance import services
from attendance.models import Assignment, AttendanceCorrection, AttendanceMark, AttendanceSession, Submission
from configuration.gates import require_module
from students.family import FamilyView


def _found(queryset, pk):
    row = queryset.filter(pk=pk).first()
    if row is None:
        raise NotFound()
    return row


class TargetInput(serializers.Serializer):
    section = serializers.UUIDField(required=False, allow_null=True)
    offering = serializers.UUIDField(required=False, allow_null=True)


class SessionInput(TargetInput):
    date = serializers.DateField()
    slot = serializers.UUIDField(required=False, allow_null=True)


class MarkInput(serializers.Serializer):
    student = serializers.UUIDField()
    code = serializers.ChoiceField(AttendanceMark.Code.choices)
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True)


class MarksInput(serializers.Serializer):
    version = serializers.IntegerField()
    marks = MarkInput(many=True)


class CorrectionInput(serializers.Serializer):
    code = serializers.ChoiceField(AttendanceMark.Code.choices)
    reason = serializers.CharField(max_length=300)


class AssignmentInput(TargetInput):
    title = serializers.CharField(max_length=150)
    instructions = serializers.CharField(max_length=4000)
    due_at = serializers.DateTimeField()


class AttendanceTeaching(TeachingView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "attendance")

    def target(self, data):
        institution = self.request.institution
        if bool(data.get("section")) == bool(data.get("offering")):
            raise serializers.ValidationError({"section": ["Choose a section or an offering."]})
        if data.get("section"):
            return _found(Section.objects.filter(institution=institution), data["section"])
        return _found(CourseOffering.objects.filter(institution=institution).select_related("course"), data["offering"])

    def session(self, pk) -> AttendanceSession:
        rows = AttendanceSession.objects.filter(institution=self.request.institution).select_related(
            "section", "offering__course"
        )
        return _found(rows, pk)


class OpenSession(AttendanceTeaching):
    def post(self, request):
        data = valid(SessionInput, request.data)
        target = self.target(data)
        slot = (
            _found(TimetableSlot.objects.filter(timetable__institution=request.institution), data["slot"])
            if data.get("slot")
            else None
        )
        session, made = services.open_session(request.user, request.institution, target, data["date"], slot)
        return Response(services.session_item(session), status=status.HTTP_201_CREATED if made else status.HTTP_200_OK)


class SessionDetail(AttendanceTeaching):
    def get(self, request, pk):
        session = self.session(pk)
        services._check(request.user, session)
        return Response(services.session_item(session))


class SaveMarks(AttendanceTeaching):
    def post(self, request, pk):
        data = valid(MarksInput, request.data)
        session = services.save_marks(request.user, self.session(pk), data["version"], data["marks"])
        return Response(services.session_item(session))


class SubmitSession(AttendanceTeaching):
    def post(self, request, pk):
        version = int(request.data.get("version", 0))
        return Response(services.session_item(services.submit(request.user, self.session(pk), version)))


class RequestCorrection(AttendanceTeaching):
    def post(self, request, mark):
        found = _found(
            AttendanceMark.objects.filter(session__institution=request.institution).select_related("session"), mark
        )
        data = valid(CorrectionInput, request.data)
        made = services.request_correction(request.user, found, data["code"], data["reason"])
        return Response(services.correction_item(made), status=status.HTTP_201_CREATED)


class TeachingAssignments(AttendanceTeaching):
    def get(self, request):
        mine = [
            a for a in Assignment.objects.filter(institution=request.institution) if services.can_see(request.user, a)
        ]
        return Response([services.assignment_item(a) for a in mine])

    def post(self, request):
        data = valid(AssignmentInput, request.data)
        target = self.target(data)
        fields = {k: data[k] for k in ("title", "instructions", "due_at")}
        made = services.post_assignment(request.user, request.institution, target, fields)
        return Response(services.assignment_item(made), status=status.HTTP_201_CREATED)


class TeachingAssignment(AttendanceTeaching):
    def get(self, request, pk):
        found = _found(Assignment.objects.filter(institution=request.institution), pk)
        if not services.can_see(request.user, found):
            raise NotFound()
        return Response(services.assignment_item(found, submissions=True))


class Feedback(AttendanceTeaching):
    def post(self, request, pk):
        found = _found(
            Submission.objects.filter(assignment__institution=request.institution).select_related("assignment"), pk
        )
        feedback = str(request.data.get("feedback", "")).strip()
        if not feedback:
            raise serializers.ValidationError({"feedback": ["Write the feedback."]})
        services.give_feedback(request.user, found, feedback)
        return Response({"id": str(found.id), "feedback": found.feedback})


class ManagerView(GenericAPIView):
    permission_classes = [IsAuthenticated, holds_any(services.MANAGE)]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "attendance")


class Corrections(ManagerView):
    def get(self, request):
        rows = AttendanceCorrection.objects.filter(institution=request.institution, state="requested").select_related(
            "mark__session__section",
            "mark__session__offering__course",
            "mark__enrollment__student__person",
            "requested_by",
        )
        return Response([services.correction_item(c) for c in rows])


class DecideCorrection(ManagerView):
    approve = True

    def post(self, request, pk):
        found = _found(AttendanceCorrection.objects.filter(institution=request.institution), pk)
        return Response(services.correction_item(services.decide_correction(request.user, found, self.approve)))


class Lock(ManagerView):
    def post(self, request, pk):
        found = _found(AttendanceSession.objects.filter(institution=request.institution), pk)
        return Response(services.session_item(services.lock(request.user, found, int(request.data.get("version", 0)))))


class StudentAttendance(GenericAPIView):
    permission_classes = [IsAuthenticated, holds_any("student.read")]

    def get(self, request, pk):
        from students.views import visible_students

        require_module(request.institution, "attendance")
        student = _found(visible_students(request.user, request.institution), pk)
        return Response(services.summary(student.enrollments.all()))


class OwnAttendance(OwnView):
    def get(self, request):
        require_module(request.institution, "attendance")
        return Response(services.summary(self.me.enrollments.all()))


class OwnAssignments(OwnView):
    def get(self, request):
        require_module(request.institution, "attendance")
        enrollment = self.me.enrollments.filter(status="active").first()
        if enrollment is None:
            return Response([])
        rows = services.for_student(enrollment).select_related("section", "offering__course")
        return Response([services.assignment_item(a, enrollment=enrollment) for a in rows])


class HandIn(OwnView):
    def post(self, request, pk):
        require_module(request.institution, "attendance")
        enrollment = self.me.enrollments.filter(status="active").first()
        found = _found(Assignment.objects.filter(institution=request.institution), pk)
        if enrollment is None:
            raise NotFound()
        text = str(request.data.get("text", "")).strip()
        if not text:
            raise serializers.ValidationError({"text": ["Write your answer."]})
        services.hand_in(enrollment, found, text)
        return Response(services.assignment_item(found, enrollment=enrollment))


class ChildAttendance(FamilyView):
    def get(self, request, pk):
        from configuration.gates import module_on

        for student, shared in self.children().items():
            if student.pk == pk and shared and module_on(request.institution, "attendance"):
                return Response(services.summary(student.enrollments.all()))
        raise NotFound()
