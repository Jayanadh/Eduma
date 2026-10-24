"""Hostels (slice 10a S10A-08, S10A-09): a bed and a student each hold at most one allocation over any dates."""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.permissions import has_perm, today_for
from campus.models import Allocation, Bed, Hostel, OutPass
from common.exceptions import Problem

MANAGE = "hostel.manage"


def require(actor, institution) -> None:
    if not has_perm(actor, institution, MANAGE):
        raise PermissionDenied("Only the warden can do this.")


def _overlaps(a: Allocation) -> Q:
    return Q(starts_on__lte=a.ends_on, ends_on__gte=a.starts_on)


def request(actor, institution, student, data: dict) -> Allocation:
    require(actor, institution)
    if data["ends_on"] < data["starts_on"]:
        raise ValidationError({"ends_on": ["End on or after the start."]})
    a = Allocation(institution=institution, student=student, **data)
    live = Allocation.objects.filter(student=student).exclude(state__in=("rejected", "checked_out"))
    if live.filter(_overlaps(a)).exists():
        raise ValidationError({"student": ["Already has a place in a hostel on these dates."]})
    a.save()
    return a


def _place(a: Allocation, bed: Bed) -> None:
    taken = Allocation.objects.filter(_overlaps(a), bed=bed, state__in=Allocation.HOLDING).exclude(pk=a.pk)
    if taken.exists():
        raise ValidationError({"bed": ["This bed is taken on these dates."]})
    a.bed = bed


def approve(actor, a: Allocation, bed: Bed) -> Allocation:
    require(actor, a.institution)
    with transaction.atomic():
        Bed.objects.select_for_update().get(pk=bed.pk)
        a = Allocation.objects.select_for_update().get(pk=a.pk)
        if a.state != Allocation.State.REQUESTED:
            raise Problem(409, "invalid_transition", "Only a request is approved.")
        _place(a, bed)
        a.state, a.decided_by = Allocation.State.APPROVED, actor
        a.save()
        return a


def step(actor, a: Allocation, to: str) -> Allocation:
    require(actor, a.institution)
    allowed = {
        "check-in": ("approved", "allocated"),
        "check-out": ("allocated", "checked_out"),
        "reject": ("requested", "rejected"),
    }
    before, after = allowed[to]
    if a.state != before:
        raise Problem(409, "invalid_transition", f"A {a.state} place can't {to.replace('-', ' ')}.")
    a.state = after
    if after == "checked_out":
        a.ends_on = min(a.ends_on, today_for(a.institution))
    a.save()
    return a


def transfer(actor, a: Allocation, bed: Bed) -> Allocation:
    """Move a resident to another bed: the old one frees as the new one is taken, in one step."""
    require(actor, a.institution)
    with transaction.atomic():
        Bed.objects.select_for_update().filter(pk__in=[bed.pk, a.bed_id]).order_by("pk")
        a = Allocation.objects.select_for_update().get(pk=a.pk)
        if a.state != Allocation.State.ALLOCATED:
            raise Problem(409, "invalid_transition", "Only a resident is transferred.")
        _place(a, bed)
        a.save()
        return a


def ask_out(student, data: dict) -> OutPass:
    today = today_for(student.institution)
    a = Allocation.objects.filter(
        student=student, state=Allocation.State.ALLOCATED, starts_on__lte=today, ends_on__gte=today
    ).first()
    if a is None:
        raise ValidationError({"allocation": ["Out-passes are for hostel residents."]})
    if data["returns_at"] <= data["leaves_at"]:
        raise ValidationError({"returns_at": ["Come back after leaving."]})
    return OutPass.objects.create(allocation=a, **data)


def decide_out(actor, out: OutPass, to: str) -> OutPass:
    require(actor, out.allocation.institution)
    moves = {
        "approve": ("requested", "approved"),
        "reject": ("requested", "rejected"),
        "returned": ("approved", "returned"),
    }
    before, after = moves[to]
    if out.state != before:
        raise Problem(409, "invalid_transition", f"A {out.state} out-pass can't be {after}.")
    out.state, out.decided_by = after, actor
    if after == "returned":
        out.returned_at = timezone.now()
    out.save()
    return out


def occupancy(hostel: Hostel) -> dict:
    today = today_for(hostel.institution)
    beds = list(hostel.beds.all())
    living = {
        a.bed_id: a.student.person.full_name
        for a in Allocation.objects.filter(
            bed__in=beds, state__in=Allocation.HOLDING, starts_on__lte=today, ends_on__gte=today
        ).select_related("student__person")
    }
    return {
        "id": str(hostel.id),
        "name": hostel.name,
        "beds": [{"id": str(b.id), "room": b.room, "label": b.label, "resident": living.get(b.id)} for b in beds],
        "occupied": len(living),
        "capacity": len(beds),
    }


def allocation_item(a: Allocation) -> dict:
    return {
        "id": str(a.id),
        "student": {"id": str(a.student_id), "number": a.student.number, "full_name": a.student.person.full_name},
        "bed": {"id": str(a.bed_id), "room": a.bed.room, "label": a.bed.label, "hostel": a.bed.hostel.name}
        if a.bed_id
        else None,
        "starts_on": a.starts_on,
        "ends_on": a.ends_on,
        "state": a.state,
    }


def out_item(o: OutPass) -> dict:
    return {
        "id": str(o.id),
        "student": o.allocation.student.person.full_name,
        "leaves_at": o.leaves_at,
        "returns_at": o.returns_at,
        "reason": o.reason,
        "state": o.state,
    }
