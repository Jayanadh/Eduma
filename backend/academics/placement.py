"""Placing students into sections for a year (slice 5a S5A-04, S5A-08): the pack's EnrollmentPeriod, one per study
episode and academic year, never more students than the section holds."""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.models import AcademicYear, EnrollmentPeriod, Section
from academics.sections import can_manage_section, placed
from common import audit
from common.exceptions import Problem
from students.models import Enrollment, Student


def _manage(actor, section: Section) -> None:
    if not can_manage_section(actor, section):
        raise PermissionDenied("Your role does not cover this section's campus.")
    if section.year.status == AcademicYear.Status.CLOSED:
        raise Problem(409, "year_closed", f"{section.year.code} is closed.")


def _locked(section: Section) -> Section:
    return (
        Section.objects.select_for_update().select_related("year", "grade", "campus", "institution").get(pk=section.pk)
    )


def _check_room(section: Section, adding: int) -> None:
    left = section.capacity - placed(section)
    if adding > left:
        raise Problem(409, "section_full", f"{section.code} has room for {max(left, 0)} more.", room=max(left, 0))


def _episodes(section: Section, student_ids: list) -> list[Enrollment]:
    """Each student's active study episode, refusing anyone who can't be placed in this section's year."""
    institution = section.institution
    students = list(Student.objects.filter(institution=institution, pk__in=student_ids).select_related("person"))
    if len(students) != len(set(student_ids)):
        raise ValidationError({"students": ["Choose students of this school."]})
    years = {year.code: year for year in institution.academic_years.all()}
    episodes, refused = [], []
    for student in students:
        episode = student.enrollments.filter(status=Enrollment.Status.ACTIVE).first()
        enrolled_for = years.get(episode.academic_year) if episode else None
        if student.status != Student.Status.ACTIVE or episode is None:
            refused.append(f"{student.number} is not enrolled")
        elif enrolled_for is not None and enrolled_for.starts_on > section.year.starts_on:
            refused.append(f"{student.number} is enrolled from {enrolled_for.code}")
        else:
            episodes.append(episode)
    if refused:
        raise ValidationError({"students": [f"Can't place: {'; '.join(refused)}."]})
    return episodes


def place(actor, section: Section, student_ids: list) -> list[EnrollmentPeriod]:
    with transaction.atomic():
        section = _locked(section)
        _manage(actor, section)
        episodes = _episodes(section, student_ids)
        taken = EnrollmentPeriod.objects.filter(enrollment__in=episodes, year=section.year).select_related(
            "enrollment__student", "section"
        )
        if taken:
            names = ", ".join(f"{row.enrollment.student.number} ({row.section.code})" for row in taken)
            raise Problem(409, "already_placed", f"Already placed this year: {names}.")
        _check_room(section, len(episodes))
        made = []
        for episode in episodes:
            made.append(
                EnrollmentPeriod.objects.create(
                    enrollment=episode,
                    institution=section.institution,
                    year=section.year,
                    section=section,
                    grade=section.grade,
                    campus=section.campus,
                    placed_by=actor,
                )
            )
            audit.log(
                actor,
                "student.placed",
                episode.student,
                f"{episode.student.number} placed in {section.code} ({section.year.code})",
                institution=section.institution,
            )
        return made


def move(actor, period: EnrollmentPeriod, target: Section) -> EnrollmentPeriod:
    if target.year_id != period.year_id:
        raise ValidationError({"section": ["Choose a section in the same academic year."]})
    with transaction.atomic():
        source = period.section
        _manage(actor, source)
        target = _locked(target)
        _manage(actor, target)
        period = EnrollmentPeriod.objects.select_for_update().get(pk=period.pk)
        if period.section_id == target.pk:
            return period
        _check_room(target, 1)
        period.section, period.grade, period.campus = target, target.grade, target.campus
        period.save()
        student = period.enrollment.student
        audit.log(
            actor,
            "student.section_changed",
            student,
            f"{student.number} moved from {source.code} to {target.code}",
            institution=target.institution,
            changes={"section": {"from": source.code, "to": target.code}},
        )
        return period


def end(actor, period: EnrollmentPeriod) -> EnrollmentPeriod:
    _manage(actor, period.section)
    period.state = EnrollmentPeriod.State.ENDED
    period.save()
    student = period.enrollment.student
    audit.log(actor, "student.placement_ended", student, f"{student.number} taken out of {period.section.code}")
    return period


def label(period: EnrollmentPeriod | None) -> str | None:
    return f"{period.grade.name} · {period.section.code}" if period else None


def current_period(student: Student) -> EnrollmentPeriod | None:
    """The student's latest active placement (this year's, or next year's once placed)."""
    return (
        EnrollmentPeriod.objects.filter(enrollment__student=student, state=EnrollmentPeriod.State.ACTIVE)
        .select_related("grade", "section", "year", "campus")
        .order_by("-year__starts_on")
        .first()
    )


def roster_item(period: EnrollmentPeriod) -> dict:
    student = period.enrollment.student
    return {
        "period": str(period.id),
        "student": {"id": str(student.id), "number": student.number, "full_name": student.person.full_name},
        "status": student.status,
        "is_repeat": period.is_repeat,
    }
