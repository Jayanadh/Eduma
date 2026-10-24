"""Rooms, timetable versions, conflicts, substitutions and a teacher's day (slice 6 S6-01..05)."""

import datetime as dt

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.models import (
    CourseOffering,
    Room,
    Section,
    Subject,
    Substitution,
    Term,
    TimetableSlot,
    TimetableVersion,
)
from academics.offerings import label as offering_label
from academics.sections import _staff
from academics.structure import MANAGE
from accounts.permissions import WHOLE, active_membership, has_perm
from common import audit
from common.exceptions import Problem

Status = TimetableVersion.Status


def _require(actor, institution) -> None:
    if not has_perm(actor, institution, MANAGE, WHOLE):
        raise PermissionDenied("Only someone who sets up academics for the whole institution can change the timetable.")


def save_room(actor, institution, room: Room | None, data: dict, version: int | None = None) -> Room:
    with transaction.atomic():
        if room is not None:
            room = Room.objects.select_for_update().get(pk=room.pk)
            room.check_version(version)
        else:
            room = Room(institution=institution)
        if "campus" in data:
            if (campus := institution.campuses.filter(pk=data.pop("campus"), is_active=True).first()) is None:
                raise ValidationError({"campus": ["Choose an active campus."]})
            room.campus = campus
        if not has_perm(actor, institution, MANAGE, ("campus", room.campus_id)):
            raise PermissionDenied("Your role does not cover this campus.")
        for name, value in data.items():
            setattr(room, name, value)
        if Room.objects.filter(institution=institution, code=room.code).exclude(pk=room.pk).exists():
            raise ValidationError({"code": ["Another room has this code."]})
        room.save()
        return room


def new_version(actor, term: Term) -> TimetableVersion:
    """A draft: a copy of the published timetable when there is one, else empty."""
    institution = term.year.institution
    _require(actor, institution)
    with transaction.atomic():
        Term.objects.select_for_update().get(pk=term.pk)
        if draft := term.timetables.filter(status=Status.DRAFT).first():
            return draft
        number = (term.timetables.aggregate(n=Max("number"))["n"] or 0) + 1
        made = TimetableVersion.objects.create(institution=institution, term=term, number=number)
        if published := term.timetables.filter(status=Status.PUBLISHED).first():
            for slot in published.slots.all():
                slot.pk, slot.timetable = None, made
                slot._state.adding = True
                slot.save()
        return made


def _draft(version: TimetableVersion) -> None:
    if version.status != Status.DRAFT:
        raise Problem(409, "invalid_transition", "Only a draft timetable changes; start a new version.")


def add_slot(actor, timetable: TimetableVersion, data: dict) -> TimetableVersion:
    institution = timetable.institution
    _require(actor, institution)
    _draft(timetable)
    if data["ends_at"] <= data["starts_at"]:
        raise ValidationError({"ends_at": ["End after the start."]})
    if bool(data.get("section")) == bool(data.get("offering")):
        raise ValidationError({"section": ["Choose a section or an offering."]})
    slot = TimetableSlot(
        timetable=timetable, weekday=data["weekday"], starts_at=data["starts_at"], ends_at=data["ends_at"]
    )
    if data.get("section"):
        slot.section = Section.objects.filter(
            institution=institution, pk=data["section"], year=timetable.term.year
        ).first()
        if slot.section is None:
            raise ValidationError({"section": ["Choose a section of this term's year."]})
    if data.get("offering"):
        slot.offering = CourseOffering.objects.filter(
            institution=institution, pk=data["offering"], term=timetable.term
        ).first()
        if slot.offering is None:
            raise ValidationError({"offering": ["Choose an offering of this term."]})
    if data.get("subject"):
        if (subject := Subject.objects.filter(institution=institution, pk=data["subject"]).first()) is None:
            raise ValidationError({"subject": ["Choose a subject."]})
        slot.subject = subject
    if data.get("room"):
        if (room := Room.objects.filter(institution=institution, pk=data["room"], is_active=True).first()) is None:
            raise ValidationError({"room": ["Choose an active room."]})
        slot.room = room
    if data.get("teacher"):
        slot.teacher = _staff(institution, data["teacher"], "teacher")
    slot.save()
    timetable.save()  # a new version number: publishing must be of what was seen
    return timetable


def remove_slot(actor, timetable: TimetableVersion, slot: TimetableSlot) -> TimetableVersion:
    _require(actor, timetable.institution)
    _draft(timetable)
    slot.delete()
    timetable.save()
    return timetable


def conflicts(timetable: TimetableVersion) -> list[dict]:
    """Pairs of slots that collide on a weekday: the same room, teacher, section or offering at overlapping times."""
    slots = list(timetable.slots.select_related("room", "teacher__user", "section", "offering__course"))
    found = []
    for i, a in enumerate(slots):
        for b in slots[i + 1 :]:
            if a.weekday != b.weekday or not (a.starts_at < b.ends_at and b.starts_at < a.ends_at):
                continue
            for kind, left, right in (
                ("room", a.room_id, b.room_id),
                ("teacher", a.teacher_id, b.teacher_id),
                ("section", a.section_id, b.section_id),
                ("offering", a.offering_id, b.offering_id),
            ):
                if left and left == right:
                    found.append({"kind": kind, "slots": [str(a.id), str(b.id)], "weekday": a.weekday,
                                  "detail": f"{_label(a)} and {_label(b)} share a {kind}"})  # fmt: skip
    return found


def publish(actor, timetable: TimetableVersion, version: int) -> TimetableVersion:
    _require(actor, timetable.institution)
    with transaction.atomic():
        timetable = TimetableVersion.objects.select_for_update().get(pk=timetable.pk)
        timetable.check_version(version)
        _draft(timetable)
        if clashes := conflicts(timetable):
            raise Problem(409, "timetable_conflict", f"Resolve {len(clashes)} clash(es) first.", conflicts=clashes)
        timetable.term.timetables.filter(status=Status.PUBLISHED).update(status=Status.SUPERSEDED)
        timetable.status, timetable.published_by, timetable.published_at = Status.PUBLISHED, actor, timezone.now()
        timetable.save()
        audit.log(
            actor,
            "timetable.published",
            timetable,
            f"Timetable {timetable.number} for {timetable.term.name} published",
            institution=timetable.institution,
        )
        return timetable


def substitute(actor, slot: TimetableSlot, data: dict) -> Substitution:
    timetable = slot.timetable
    _require(actor, timetable.institution)
    date: dt.date = data["date"]
    if timetable.status != Status.PUBLISHED:
        raise ValidationError({"slot": ["Choose a lesson of the published timetable."]})
    if not timetable.term.starts_on <= date <= timetable.term.ends_on or date.isoweekday() != slot.weekday:
        raise ValidationError({"date": ["Choose a day this lesson happens."]})
    teacher = _staff(timetable.institution, data["teacher"], "teacher")
    made, _ = Substitution.objects.update_or_create(
        slot=slot, date=date, defaults={"teacher": teacher, "reason": data["reason"], "created_by": actor}
    )
    audit.log(
        actor,
        "timetable.substituted",
        timetable,
        f"{teacher.user.full_name} takes {_label(slot)} on {date}",
        institution=timetable.institution,
    )
    return made


def _label(slot: TimetableSlot) -> str:
    return slot.section.code if slot.section_id else offering_label(slot.offering)


def target(slot) -> dict:
    if slot.section_id:
        return {"kind": "section", "id": str(slot.section_id), "label": slot.section.code}
    return {"kind": "offering", "id": str(slot.offering_id), "label": offering_label(slot.offering)}


def slot_item(slot: TimetableSlot) -> dict:
    return {
        "id": str(slot.id),
        "weekday": slot.weekday,
        "starts_at": slot.starts_at.strftime("%H:%M"),
        "ends_at": slot.ends_at.strftime("%H:%M"),
        "target": target(slot),
        "subject": slot.subject.name if slot.subject_id else None,
        "room": {"id": str(slot.room_id), "code": slot.room.code} if slot.room_id else None,
        "teacher": {"id": str(slot.teacher_id), "full_name": slot.teacher.user.full_name} if slot.teacher_id else None,
    }


def timetable_item(timetable: TimetableVersion) -> dict:
    slots = timetable.slots.select_related("section", "offering__course", "subject", "room", "teacher__user")
    return {
        "id": str(timetable.id),
        "version": timetable.version,
        "number": timetable.number,
        "status": timetable.status,
        "status_label": timetable.get_status_display(),
        "term": {"id": str(timetable.term_id), "name": timetable.term.name, "year": timetable.term.year.code},
        "slots": [slot_item(s) for s in slots],
        "conflicts": conflicts(timetable) if timetable.status == Status.DRAFT else [],
    }


def room_item(room: Room) -> dict:
    return {
        "id": str(room.id),
        "version": room.version,
        "code": room.code,
        "name": room.name,
        "capacity": room.capacity,
        "campus": {"id": str(room.campus_id), "name": room.campus.name},
        "is_active": room.is_active,
    }


def day(user, institution, date: dt.date) -> list[dict]:
    """The teacher's lessons that day from published timetables: their own unless someone covers, plus covers."""
    from attendance.models import AttendanceSession

    membership = active_membership(user, institution)
    if membership is None:
        return []
    published = TimetableSlot.objects.filter(
        timetable__institution=institution,
        timetable__status=Status.PUBLISHED,
        timetable__term__starts_on__lte=date,
        timetable__term__ends_on__gte=date,
        weekday=date.isoweekday(),
    ).select_related("section", "offering__course", "subject", "room", "teacher__user")
    covered = set(Substitution.objects.filter(date=date, slot__in=published).values_list("slot_id", flat=True))
    covering = set(Substitution.objects.filter(date=date, teacher=membership).values_list("slot_id", flat=True))
    found = []
    for slot in published:
        mine = slot.teacher_id == membership.id and slot.id not in covered
        if not (mine or slot.id in covering):
            continue
        scope = {"section": slot.section} if slot.section_id else {"offering": slot.offering}
        session = AttendanceSession.objects.filter(date=date, slot=slot, **scope).first()
        found.append(
            {
                **slot_item(slot),
                "substitute": slot.id in covering,
                "session": {"id": str(session.id), "state": session.state} if session else None,
            }
        )
    return found
