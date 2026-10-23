"""Moving a section on to next year (slice 5a S5A-06, TST-035): new placements in the later year inside each
student's existing study episode; last year's placement stays; a re-run places nobody twice."""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from academics.models import EnrollmentPeriod, Section
from academics.placement import check_room, require_manageable
from common import audit
from students.models import Enrollment, Student

MODES = ("promote", "repeat")


def _check(source: Section, target: Section, mode: str) -> None:
    if target.year.starts_on <= source.year.starts_on:
        raise ValidationError({"target": ["Choose a section in a later academic year."]})
    if mode == "repeat" and target.grade_id != source.grade_id:
        raise ValidationError({"mode": ["Repeating keeps the same grade."]})
    if mode == "promote" and target.grade_id == source.grade_id:
        raise ValidationError({"mode": ["Moving up goes to another grade; choose repeat to keep the grade."]})


def _rows(source: Section, target: Section) -> list[dict]:
    """Everyone placed in the source section, with what moving up would do for them."""
    already = set(
        EnrollmentPeriod.objects.filter(
            year=target.year, enrollment__student__institution=source.institution
        ).values_list("enrollment__student_id", flat=True)
    )
    rows = []
    periods = source.placements.select_related("enrollment__student__person").order_by("enrollment__student__number")
    for period in periods:
        student, episode = period.enrollment.student, period.enrollment
        if student.status == Student.Status.WITHDRAWN:
            action = "withdrawn"
        elif episode.status != Enrollment.Status.ACTIVE:
            action = "not_enrolled"
        elif student.id in already:
            action = "already_placed"
        else:
            action = "move"
        rows.append(
            {
                "student": {"id": str(student.id), "number": student.number, "full_name": student.person.full_name},
                "action": action,
                "episode": episode,
            }
        )
    return rows


def preview(actor, source: Section, target: Section, mode: str) -> list[dict]:
    require_manageable(actor, source)
    require_manageable(actor, target)
    _check(source, target, mode)
    return [{key: value for key, value in row.items() if key != "episode"} for row in _rows(source, target)]


def commit(actor, source: Section, target: Section, mode: str, student_ids: list) -> dict:
    wanted = {str(pk) for pk in student_ids}
    with transaction.atomic():
        list(Section.objects.select_for_update().filter(pk__in=[source.pk, target.pk]).order_by("pk"))  # fixed order
        fresh = Section.objects.select_related("year", "grade", "campus", "institution")
        source, target = fresh.get(pk=source.pk), fresh.get(pk=target.pk)
        require_manageable(actor, source)
        require_manageable(actor, target)
        _check(source, target, mode)
        moving = [row for row in _rows(source, target) if row["action"] == "move" and row["student"]["id"] in wanted]
        check_room(target, len(moving))
        for row in moving:
            EnrollmentPeriod.objects.create(
                enrollment=row["episode"],
                institution=target.institution,
                year=target.year,
                section=target,
                grade=target.grade,
                campus=target.campus,
                is_repeat=mode == "repeat",
                placed_by=actor,
            )
            audit.log(
                actor,
                "student.placed",
                row["episode"].student,
                f"{row['student']['number']} moved up from {source.code} to {target.code} ({target.year.code})",
                institution=target.institution,
            )
        audit.log(
            actor,
            "section.moved_up",
            source,
            f"{len(moving)} moved from {source.code} ({source.year.code}) to {target.code} ({target.year.code})",
            institution=source.institution,
            changes={"moved": len(moving), "mode": mode},
        )
        return {"moved": len(moving)}
