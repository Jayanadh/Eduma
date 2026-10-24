"""Library, transport and hostel for staff (institution/campus/), students (student/campus) and guardians
(family/children/<id>/transport) — slice 10a."""

from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.registration_views import OwnView
from academics.views import valid
from accounts.models import Membership
from accounts.role_views import holds_any
from campus import hostel, library, transport
from campus.models import Allocation, Bed, Fine, Hostel, Loan, OutPass, Rider, Route, Title, Trip, Vehicle
from configuration.gates import module_on, require_module
from students.family import FamilyView


def _found(queryset, pk):
    row = queryset.filter(pk=pk).first()
    if row is None:
        raise NotFound()
    return row


class CampusView(GenericAPIView):
    permission_classes = [IsAuthenticated, holds_any("institution.read")]
    module = "library"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, self.module)

    def student(self, pk):
        return _found(self.request.institution.students.select_related("person"), pk)


# Library


class Titles(CampusView):
    def get(self, request):
        rows = Title.objects.filter(institution=request.institution).prefetch_related("copies")
        if len(q := request.query_params.get("search", "").strip()) >= 3:
            rows = rows.filter(title__icontains=q)
        return Response([library.title_item(t) for t in rows[:100]])

    def post(self, request):
        data = {
            k: request.data.get(k) for k in ("title", "author", "isbn", "subject") if request.data.get(k) is not None
        }
        if not str(data.get("title", "")).strip():
            raise serializers.ValidationError({"title": ["Give the title."]})
        if request.data.get("replacement_cost"):
            data["replacement_cost"] = request.data["replacement_cost"]
        data["copies"] = [str(a).strip() for a in request.data.get("copies", []) if str(a).strip()]
        return Response(
            library.title_item(library.add_title(request.user, request.institution, data)),
            status=status.HTTP_201_CREATED,
        )


class Loans(CampusView):
    def get(self, request):
        rows = Loan.objects.filter(copy__title__institution=request.institution).select_related(
            "copy__title", "student__person", "staff__user"
        )
        if request.query_params.get("active"):
            rows = rows.filter(status="active")
        return Response([library.loan_item(x) for x in rows[:200]])

    def post(self, request):
        student = self.student(request.data["student"]) if request.data.get("student") else None
        staff = (
            None
            if student
            else _found(
                Membership.objects.filter(institution=request.institution, kind="staff"), request.data.get("staff")
            )
        )
        loan = library.issue(
            request.user,
            request.institution,
            str(request.data.get("accession", "")).strip(),
            student=student,
            staff=staff,
        )
        return Response(library.loan_item(loan), status=status.HTTP_201_CREATED)


class LoanAction(CampusView):
    action = "return"

    def post(self, request, pk):
        loan = _found(
            Loan.objects.filter(copy__title__institution=request.institution).select_related("copy__title"), pk
        )
        done = {"return": library.give_back, "renew": library.renew, "lost": library.lose}[self.action](
            request.user, loan
        )
        return Response(library.loan_item(done))


class Reservations(CampusView):
    def post(self, request):
        title = _found(Title.objects.filter(institution=request.institution), request.data.get("title"))
        student = self.student(request.data["student"]) if request.data.get("student") else None
        staff = (
            None
            if student
            else _found(
                Membership.objects.filter(institution=request.institution, kind="staff"), request.data.get("staff")
            )
        )
        made = library.reserve(request.user, request.institution, title, student=student, staff=staff)
        return Response({"id": str(made.id)}, status=status.HTTP_201_CREATED)


class Waive(CampusView):
    def post(self, request, pk):
        fine = _found(
            Fine.objects.filter(loan__copy__title__institution=request.institution).select_related("loan__copy__title"),
            pk,
        )
        library.waive(request.user, fine, str(request.data.get("reason", "")))
        return Response(library.loan_item(fine.loan))


# Transport


class TransportView(CampusView):
    module = "transport"


class Vehicles(TransportView):
    def get(self, request):
        return Response(
            [
                {"id": str(v.id), "registration": v.registration, "capacity": v.capacity}
                for v in Vehicle.objects.filter(institution=request.institution)
            ]
        )

    def post(self, request):
        data = {
            "registration": str(request.data.get("registration", "")).strip(),
            "capacity": int(request.data.get("capacity") or 0),
        }
        if not data["registration"] or data["capacity"] < 1:
            raise serializers.ValidationError({"registration": ["Give the registration and the seats."]})
        v = transport.add_vehicle(request.user, request.institution, data)
        return Response(
            {"id": str(v.id), "registration": v.registration, "capacity": v.capacity}, status=status.HTTP_201_CREATED
        )


def route_item(r: Route) -> dict:
    return {
        "id": str(r.id),
        "name": r.name,
        "vehicle": r.vehicle.registration,
        "capacity": r.vehicle.capacity,
        "stops": r.stops,
    }


class Routes(TransportView):
    def get(self, request):
        return Response(
            [route_item(r) for r in Route.objects.filter(institution=request.institution).select_related("vehicle")]
        )

    def post(self, request):
        vehicle = _found(Vehicle.objects.filter(institution=request.institution), request.data.get("vehicle"))
        stops = [
            {"name": str(s["name"]).strip(), "time": str(s.get("time", ""))}
            for s in request.data.get("stops", [])
            if s.get("name")
        ]
        made = transport.add_route(
            request.user,
            request.institution,
            {"name": str(request.data.get("name", "")).strip(), "vehicle": vehicle, "stops": stops},
        )
        return Response(route_item(made), status=status.HTTP_201_CREATED)


class RiderInput(serializers.Serializer):
    route = serializers.UUIDField()
    student = serializers.UUIDField()
    stop = serializers.CharField(max_length=80)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()


class Riders(TransportView):
    def get(self, request):
        rows = Rider.objects.filter(route__institution=request.institution).select_related("route", "student__person")
        return Response(
            [
                {
                    "id": str(r.id),
                    "route": r.route.name,
                    "student": r.student.person.full_name,
                    "stop": r.stop,
                    "starts_on": r.starts_on,
                    "ends_on": r.ends_on,
                }
                for r in rows
            ]
        )

    def post(self, request):
        data = valid(RiderInput, request.data)
        route = _found(
            Route.objects.filter(institution=request.institution).select_related("vehicle"), data.pop("route")
        )
        made = transport.assign(request.user, route, self.student(data.pop("student")), data)
        return Response({"id": str(made.id)}, status=status.HTTP_201_CREATED)


class Pickups(TransportView):
    def post(self, request):
        student = self.student(request.data.get("student"))
        data = {
            "full_name": str(request.data.get("full_name", "")).strip(),
            "relationship": str(request.data.get("relationship", "")).strip(),
        }
        if not data["full_name"]:
            raise serializers.ValidationError({"full_name": ["Give the name."]})
        transport.add_pickup(request.user, student, data)
        return Response({"approved": transport.approved_pickups(student)}, status=status.HTTP_201_CREATED)


class TripInput(serializers.Serializer):
    route = serializers.UUIDField()
    date = serializers.DateField()
    direction = serializers.ChoiceField(["to_school", "home"])
    driver = serializers.UUIDField(required=False, allow_null=True)
    attendant = serializers.UUIDField(required=False, allow_null=True)


class Trips(TransportView):
    def get(self, request):
        rows = Trip.objects.filter(route__institution=request.institution).select_related("route")
        if date := request.query_params.get("date"):
            rows = rows.filter(date=date)
        mine = [t for t in rows.order_by("-date") if transport._crew(request.user, t)]
        return Response([transport.trip_item(t) for t in mine[:100]])

    def post(self, request):
        data = valid(TripInput, request.data)
        route = _found(Route.objects.filter(institution=request.institution), data.pop("route"))
        staff = Membership.objects.filter(institution=request.institution, kind="staff")
        for role in ("driver", "attendant"):
            data[role] = _found(staff, data[role]) if data.get(role) else None
        return Response(
            transport.trip_item(transport.plan_trip(request.user, route, data)), status=status.HTTP_201_CREATED
        )


class TripAction(TransportView):
    action = "board"

    def post(self, request, pk):
        trip = _found(Trip.objects.filter(route__institution=request.institution).select_related("route"), pk)
        if not transport._crew(request.user, trip):
            raise NotFound()
        if self.action == "state":
            transport.move(request.user, trip, str(request.data.get("state", "")))
            return Response(transport.trip_item(trip))
        student = self.student(request.data.get("student"))
        if self.action == "board":
            transport.board(request.user, trip, student)
            return Response(transport.trip_item(trip), status=status.HTTP_201_CREATED)
        transport.drop(request.user, trip, student, str(request.data.get("handed_to", "")))
        return Response(transport.trip_item(trip))


# Hostel


class HostelView(CampusView):
    module = "hostel"


class Hostels(HostelView):
    def get(self, request):
        return Response([hostel.occupancy(h) for h in Hostel.objects.filter(institution=request.institution)])

    def post(self, request):
        hostel.require(request.user, request.institution)
        made = Hostel.objects.create(
            institution=request.institution, name=str(request.data.get("name", "")).strip() or "Hostel"
        )
        return Response(hostel.occupancy(made), status=status.HTTP_201_CREATED)


class HostelDetail(HostelView):
    def get(self, request, pk):
        return Response(hostel.occupancy(_found(Hostel.objects.filter(institution=request.institution), pk)))


class Beds(HostelView):
    def post(self, request, pk):
        found = _found(Hostel.objects.filter(institution=request.institution), pk)
        hostel.require(request.user, request.institution)
        bed, _ = Bed.objects.get_or_create(
            hostel=found,
            room=str(request.data.get("room", "")).strip(),
            label=str(request.data.get("label", "")).strip(),
        )
        return Response({"id": str(bed.id), "room": bed.room, "label": bed.label}, status=status.HTTP_201_CREATED)


class StayInput(serializers.Serializer):
    student = serializers.UUIDField()
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()


def _allocations(institution):
    return Allocation.objects.filter(institution=institution).select_related("student__person", "bed__hostel")


class Allocations(HostelView):
    def get(self, request):
        return Response([hostel.allocation_item(a) for a in _allocations(request.institution).order_by("-starts_on")])

    def post(self, request):
        data = valid(StayInput, request.data)
        made = hostel.request(request.user, request.institution, self.student(data.pop("student")), data)
        return Response(hostel.allocation_item(made), status=status.HTTP_201_CREATED)


class AllocationAction(HostelView):
    action = "approve"

    def post(self, request, pk):
        a = _found(_allocations(request.institution), pk)
        if self.action in ("approve", "transfer"):
            bed = _found(Bed.objects.filter(hostel__institution=request.institution), request.data.get("bed"))
            done = (hostel.approve if self.action == "approve" else hostel.transfer)(request.user, a, bed)
        else:
            done = hostel.step(request.user, a, self.action)
        return Response(hostel.allocation_item(_found(_allocations(request.institution), done.pk)))


class OutPasses(HostelView):
    def get(self, request):
        rows = OutPass.objects.filter(allocation__institution=request.institution).select_related(
            "allocation__student__person"
        )
        return Response([hostel.out_item(o) for o in rows.order_by("-leaves_at")[:100]])


class OutPassAction(HostelView):
    action = "approve"

    def post(self, request, pk):
        out = _found(
            OutPass.objects.filter(allocation__institution=request.institution).select_related(
                "allocation__student__person"
            ),
            pk,
        )
        return Response(hostel.out_item(hostel.decide_out(request.user, out, self.action)))


# Students and guardians


class OwnCampus(OwnView):
    module = None  # each part shows only while its own module is on

    def get(self, request):
        institution, me = request.institution, self.me
        loans = (
            Loan.objects.filter(student=me).select_related("copy__title") if module_on(institution, "library") else []
        )
        stays = (
            _allocations(institution).filter(student=me).exclude(state__in=("rejected", "checked_out"))
            if module_on(institution, "hostel")
            else []
        )
        stay = next(iter(stays), None)
        outs = (
            OutPass.objects.filter(allocation__student=me).select_related("allocation__student__person") if stay else []
        )
        return Response(
            {
                "loans": [library.loan_item(x) for x in loans],
                "transport": transport.child_view(me) if module_on(institution, "transport") else None,
                "hostel": {
                    **hostel.allocation_item(stay),
                    "bed": f"{stay.bed.room} {stay.bed.label}" if stay.bed_id else None,
                }
                if stay
                else None,
                "out_passes": [hostel.out_item(o) for o in outs],
            }
        )


class OwnOutPass(OwnView):
    module = "hostel"

    def post(self, request):
        data = {
            "leaves_at": serializers.DateTimeField().to_internal_value(request.data.get("leaves_at")),
            "returns_at": serializers.DateTimeField().to_internal_value(request.data.get("returns_at")),
            "reason": str(request.data.get("reason", "")).strip(),
        }
        return Response(hostel.out_item(hostel.ask_out(self.me, data)), status=status.HTTP_201_CREATED)


class ChildTransport(FamilyView):
    def get(self, request, pk):
        if not module_on(request.institution, "transport"):
            raise NotFound()
        for student, shared in self.children().items():
            if student.pk == pk and shared:
                return Response(transport.child_view(student))
        raise NotFound()
