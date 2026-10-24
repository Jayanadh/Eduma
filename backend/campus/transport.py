"""Transport (slice 10a S10A-05..07): route capacity over overlapping dates, one boarding per rider per trip, and
drop-off only to an approved pickup."""

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.permissions import active_membership, has_perm, today_for
from campus.models import Boarding, Pickup, Rider, Route, Trip, Vehicle
from common.exceptions import Problem
from students.models import GuardianLink

MANAGE = "transport.manage"
FORWARD = {
    "planned": {"dispatched", "canceled"},
    "dispatched": {"in_progress", "canceled"},
    "in_progress": {"completed"},
}


def require(actor, institution) -> None:
    if not has_perm(actor, institution, MANAGE):
        raise PermissionDenied("Only the transport office can do this.")


def add_vehicle(actor, institution, data: dict) -> Vehicle:
    require(actor, institution)
    return Vehicle.objects.create(institution=institution, **data)


def add_route(actor, institution, data: dict) -> Route:
    require(actor, institution)
    return Route.objects.create(institution=institution, **data)


def assign(actor, route: Route, student, data: dict) -> Rider:
    require(actor, route.institution)
    if data["ends_on"] < data["starts_on"]:
        raise ValidationError({"ends_on": ["End on or after the start."]})
    overlap = Q(starts_on__lte=data["ends_on"], ends_on__gte=data["starts_on"])
    with transaction.atomic():
        Route.objects.select_for_update().get(pk=route.pk)
        if Rider.objects.filter(overlap, student=student).exists():
            raise ValidationError({"student": ["Already on a route on these dates."]})
        if route.riders.filter(overlap).count() >= route.vehicle.capacity:
            raise ValidationError(
                {"route": [f"The vehicle seats {route.vehicle.capacity}; it is full on these dates."]}
            )
        if data["stop"] not in [s["name"] for s in route.stops]:
            raise ValidationError({"stop": ["Choose one of the route's stops."]})
        return Rider.objects.create(route=route, student=student, **data)


def add_pickup(actor, student, data: dict) -> Pickup:
    require(actor, student.institution)
    return Pickup.objects.create(student=student, added_by=actor, **data)


def approved_pickups(student) -> list[str]:
    """Guardians with an active link, and the people the office has named."""
    today = today_for(student.institution)
    links = GuardianLink.objects.filter(student=student, status=GuardianLink.Status.ACTIVE).filter(
        Q(ends_on__isnull=True) | Q(ends_on__gte=today)
    )
    return [link.adult.full_name for link in links.select_related("adult")] + [
        p.full_name for p in student.pickups.all()
    ]


def plan_trip(actor, route: Route, data: dict) -> Trip:
    require(actor, route.institution)
    try:
        return Trip.objects.create(route=route, **data)
    except IntegrityError as error:
        raise ValidationError({"date": ["This route already has that trip."]}) from error


def _crew(user, trip: Trip) -> bool:
    institution = trip.route.institution
    me = active_membership(user, institution)
    return has_perm(user, institution, MANAGE) or (me is not None and me.id in (trip.driver_id, trip.attendant_id))


def move(actor, trip: Trip, state: str) -> Trip:
    if not _crew(actor, trip):
        raise NotFound()
    if state not in FORWARD.get(trip.state, set()):
        raise Problem(409, "invalid_transition", f"A {trip.state} trip can't become {state}.")
    trip.state = state
    trip.save()
    return trip


def _rider(trip: Trip, student) -> Rider:
    rider = trip.route.riders.filter(student=student, starts_on__lte=trip.date, ends_on__gte=trip.date).first()
    if rider is None:
        raise ValidationError({"student": ["Not a rider on this route that day."]})
    return rider


def board(actor, trip: Trip, student) -> Boarding:
    if not _crew(actor, trip):
        raise NotFound()
    _rider(trip, student)
    try:
        with transaction.atomic():
            return Boarding.objects.create(trip=trip, student=student, boarded_at=timezone.now(), recorded_by=actor)
    except IntegrityError as error:
        raise Problem(409, "already_boarded", "Already on board.") from error


def drop(actor, trip: Trip, student, handed_to: str) -> Boarding:
    if not _crew(actor, trip):
        raise NotFound()
    boarding = trip.boardings.filter(student=student).first()
    if boarding is None:
        raise ValidationError({"student": ["Not on board."]})
    if handed_to.strip().lower() not in [name.lower() for name in approved_pickups(student)]:
        raise ValidationError(
            {"handed_to": ["Not an approved pickup for this student; keep them on the bus and call the office."]}
        )
    boarding.dropped_at, boarding.handed_to = timezone.now(), handed_to.strip()
    boarding.save()
    return boarding


def child_view(student) -> dict | None:
    """What a guardian sees: their child's route, stop and today's trips — nothing about other riders."""
    today = today_for(student.institution)
    rider = (
        Rider.objects.filter(student=student, starts_on__lte=today, ends_on__gte=today).select_related("route").first()
    )
    if rider is None:
        return None
    trips = rider.route.trips.filter(date=today)
    return {
        "route": rider.route.name,
        "stop": rider.stop,
        "time": next((s.get("time") for s in rider.route.stops if s["name"] == rider.stop), None),
        "today": [{"direction": t.direction, "state": t.state} for t in trips],
    }


def trip_item(trip: Trip) -> dict:
    return {
        "id": str(trip.id),
        "route": trip.route.name,
        "date": trip.date,
        "direction": trip.direction,
        "state": trip.state,
        "riders": [
            {"student": str(r.student_id), "name": r.student.person.full_name, "stop": r.stop}
            for r in trip.route.riders.filter(starts_on__lte=trip.date, ends_on__gte=trip.date).select_related(
                "student__person"
            )
        ],
        "boardings": [
            {
                "student": str(b.student_id),
                "boarded_at": b.boarded_at,
                "dropped_at": b.dropped_at,
                "handed_to": b.handed_to,
            }
            for b in trip.boardings.all()
        ],
    }
