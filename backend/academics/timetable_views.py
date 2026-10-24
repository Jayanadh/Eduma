"""Rooms and timetables (institution/academics/) and a teacher's day (teaching/day) — slice 6."""

import datetime as dt

from rest_framework import serializers, status
from rest_framework.response import Response

from academics import timetable
from academics.models import Room, Term, TimetableSlot, TimetableVersion
from academics.teaching import TeachingView
from academics.views import AcademicsView, valid


class RoomInput(serializers.Serializer):
    campus = serializers.UUIDField()
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=80)
    capacity = serializers.IntegerField(min_value=1, max_value=2000, required=False)


class RoomPatch(RoomInput):
    version = serializers.IntegerField()
    campus = serializers.UUIDField(required=False)
    code = serializers.CharField(max_length=20, required=False)
    name = serializers.CharField(max_length=80, required=False)
    is_active = serializers.BooleanField(required=False)


class SlotInput(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=1, max_value=7)
    starts_at = serializers.TimeField()
    ends_at = serializers.TimeField()
    section = serializers.UUIDField(required=False, allow_null=True)
    subject = serializers.UUIDField(required=False, allow_null=True)
    offering = serializers.UUIDField(required=False, allow_null=True)
    room = serializers.UUIDField(required=False, allow_null=True)
    teacher = serializers.UUIDField(required=False, allow_null=True)


class SubstitutionInput(serializers.Serializer):
    slot = serializers.UUIDField()
    date = serializers.DateField()
    teacher = serializers.UUIDField()
    reason = serializers.CharField(max_length=200)


class Rooms(AcademicsView):
    def get(self, request):
        rows = Room.objects.filter(institution=request.institution).select_related("campus")
        return Response([timetable.room_item(r) for r in rows])

    def post(self, request):
        room = timetable.save_room(request.user, request.institution, None, valid(RoomInput, request.data))
        return Response(timetable.room_item(room), status=status.HTTP_201_CREATED)


class RoomDetail(AcademicsView):
    def patch(self, request, pk):
        found = self.found(Room.objects.filter(institution=request.institution), pk)
        data = valid(RoomPatch, request.data)
        room = timetable.save_room(request.user, request.institution, found, data, data.pop("version"))
        return Response(timetable.room_item(room))


class Timetables(AcademicsView):
    def get(self, request):
        rows = TimetableVersion.objects.filter(institution=request.institution).select_related("term__year")
        if term := request.query_params.get("term"):
            rows = rows.filter(term_id=term)
        return Response([timetable.timetable_item(t) for t in rows])

    def post(self, request):
        terms = Term.objects.filter(year__institution=request.institution).select_related("year")
        term = self.found(terms, request.data.get("term"))
        return Response(
            timetable.timetable_item(timetable.new_version(request.user, term)), status=status.HTTP_201_CREATED
        )


class TimetableView(AcademicsView):
    def timetable(self) -> TimetableVersion:
        rows = TimetableVersion.objects.filter(institution=self.request.institution).select_related("term__year")
        return self.found(rows, self.kwargs["pk"])


class TimetableDetail(TimetableView):
    def get(self, request, pk):
        return Response(timetable.timetable_item(self.timetable()))


class Slots(TimetableView):
    def post(self, request, pk):
        made = timetable.add_slot(request.user, self.timetable(), valid(SlotInput, request.data))
        return Response(timetable.timetable_item(made), status=status.HTTP_201_CREATED)


class SlotDetail(TimetableView):
    def delete(self, request, pk, slot):
        found = self.timetable()
        return Response(
            timetable.timetable_item(timetable.remove_slot(request.user, found, self.found(found.slots.all(), slot)))
        )


class Publish(TimetableView):
    def post(self, request, pk):
        version = int(request.data.get("version", 0))
        return Response(timetable.timetable_item(timetable.publish(request.user, self.timetable(), version)))


class Substitutions(AcademicsView):
    def post(self, request):
        data = valid(SubstitutionInput, request.data)
        slots = TimetableSlot.objects.filter(timetable__institution=request.institution).select_related(
            "timetable__term"
        )
        made = timetable.substitute(request.user, self.found(slots, data.pop("slot")), data)
        return Response(
            {"id": str(made.id), "date": made.date, "teacher": made.teacher.user.full_name},
            status=status.HTTP_201_CREATED,
        )


class Day(TeachingView):
    def get(self, request):
        try:
            date = dt.date.fromisoformat(request.query_params.get("date", ""))
        except ValueError:
            from accounts.permissions import today_for

            date = today_for(request.institution)
        return Response(timetable.day(request.user, request.institution, date))
