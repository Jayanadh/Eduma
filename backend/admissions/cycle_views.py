"""Admission cycles for staff (slice 4a spec §5)."""

from django.db.models import Count, Q
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.role_views import holds_any
from admissions import cycles
from admissions.models import AdmissionCycle
from common.pagination import Pages
from configuration.gates import require_module
from sites.permissions import member_with


def place_in_use(place) -> int:
    """Seats taken: offers not yet expired, acceptances and enrollments."""
    from accounts.permissions import today_for
    from admissions.review import seats_in_use

    return seats_in_use(place, today_for(place.cycle.institution))


def cycle_item(cycle: AdmissionCycle) -> dict:
    stages = dict(cycle.applications.values_list("stage").annotate(n=Count("id")))
    return {
        "id": str(cycle.id),
        "name": cycle.name,
        "entry_year": cycle.entry_year,
        "academic_year": cycle.academic_year,
        "opens_on": cycle.opens_on,
        "closes_on": cycle.closes_on,
        "instructions": cycle.instructions,
        "status": cycle.status,
        "version": cycle.version,
        "places": [
            {
                "id": str(place.id),
                "code": place.code,
                "label": place.label,
                "campus": {"id": str(place.campus_id), "name": place.campus.name} if place.campus_id else None,
                "seats": place.seats,
                "program": {"id": str(place.program_id), "code": place.program.code, "name": place.program.name}
                if place.program_id
                else None,
                "in_use": place_in_use(place),
            }
            for place in cycle.places.select_related("campus", "program")
        ],
        "questions": list(cycle.questions.values("code", "label", "help", "kind", "options", "required")),
        "documents": list(cycle.documents.values("code", "label", "help", "required")),
        "counts": stages,
    }


class CycleView(GenericAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "admissions")

    def get_permissions(self):
        if self.request.method == "GET":
            return [holds_any("admission_cycle.manage", "application.review", "admission.approve")()]
        return [member_with("admission_cycle.manage")()]

    def cycle(self) -> AdmissionCycle:
        found = self.request.institution.cycles.filter(pk=self.kwargs["pk"]).first()
        if found is None:
            raise NotFound()
        return found

    def data(self, serializer_class):
        found = serializer_class(data=self.request.data, context={"institution": self.request.institution})
        found.is_valid(raise_exception=True)
        return found.validated_data


class CycleList(CycleView):
    pagination_class = Pages

    def get(self, request):
        queryset = request.institution.cycles.all()
        if len(search := request.query_params.get("search", "").strip()) >= 3:
            queryset = queryset.filter(Q(name__icontains=search) | Q(academic_year__icontains=search))
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([cycle_item(cycle) for cycle in page])

    def post(self, request):
        cycle = cycles.save_cycle(request.institution, request.user, None, self.data(cycles.CycleInput))
        return Response(cycle_item(cycle), status=status.HTTP_201_CREATED)


class CycleDetail(CycleView):
    def get(self, request, pk):
        return Response(cycle_item(self.cycle()))

    def patch(self, request, pk):
        found = self.cycle()
        cycle = cycles.save_cycle(request.institution, request.user, found, self.data(cycles.CycleInput))
        return Response(cycle_item(cycle))


class VersionView(CycleView):
    def version(self) -> int:
        from configuration.serializers import VersionInput

        return self.data(VersionInput)["version"]


class Publish(VersionView):
    def post(self, request, pk):
        found = self.cycle()
        return Response(cycle_item(cycles.publish(request.user, found, self.version())))


class Close(VersionView):
    def post(self, request, pk):
        found = self.cycle()
        return Response(cycle_item(cycles.close(request.user, found, self.version())))
