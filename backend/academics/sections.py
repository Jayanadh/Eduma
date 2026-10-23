"""Sections and who teaches them (slice 5a S5A-03, S5A-05): managed by academic_structure.manage covering the
section's campus."""

import datetime as dt

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.models import AcademicYear, EnrollmentPeriod, Section, Subject, TeachingAssignment
from academics.structure import MANAGE
from accounts.models import Membership
from accounts.permissions import has_perm, today_for
from common import audit
from common.exceptions import Problem


def can_manage_campus(actor, institution, campus_id) -> bool:
    return has_perm(actor, institution, MANAGE, ("campus", campus_id))


def can_manage_section(actor, section: Section) -> bool:
    return can_manage_campus(actor, section.institution, section.campus_id)


def placed(section: Section) -> int:
    return section.placements.filter(state=EnrollmentPeriod.State.ACTIVE).count()


def _open(year: AcademicYear) -> None:
    if year.status == AcademicYear.Status.CLOSED:
        raise Problem(409, "year_closed", f"{year.code} is closed; its sections can't change.")


def _staff(institution, membership_id, field: str) -> Membership | None:
    if membership_id is None:
        return None
    found = Membership.objects.filter(
        pk=membership_id, institution=institution, kind=Membership.Kind.STAFF, status=Membership.Status.ACTIVE
    ).first()
    if found is None:
        raise ValidationError({field: ["Choose a member of staff here."]})
    return found


def save_section(actor, institution, section: Section | None, data: dict, version: int | None = None) -> Section:
    with transaction.atomic():
        if section is not None:
            section = Section.objects.select_for_update().select_related("year").get(pk=section.pk)
            section.check_version(version)
            if not can_manage_section(actor, section):
                raise PermissionDenied("Your role does not cover this section's campus.")
            _open(section.year)  # the year it is in now: a closed year's section can't be moved out of it
            if placed(section):
                # Placements carry the section's year, grade and campus; changing them would contradict the rosters.
                moving = {name: data[name] for name in ("year", "grade", "campus") if name in data}
                current = {"year": section.year_id, "grade": section.grade_id, "campus": section.campus_id}
                if changed := [name for name, value in moving.items() if str(value) != str(current[name])]:
                    raise ValidationError(
                        {changed[0]: ["Students are placed here; take them out before changing this."]}
                    )
        else:
            section = Section(institution=institution)
        if "year" in data:
            found = institution.academic_years.filter(pk=data["year"]).first()
            if found is None:
                raise ValidationError({"year": ["Choose one of this school's academic years."]})
            section.year = found
        if "grade" in data:
            found = institution.grades.filter(pk=data["grade"], is_active=True).first()
            if found is None:
                raise ValidationError({"grade": ["Choose an active grade."]})
            section.grade = found
        if "campus" in data:
            found = institution.campuses.filter(pk=data["campus"], is_active=True).first()
            if found is None:
                raise ValidationError({"campus": ["Choose an active campus."]})
            section.campus = found
        if not can_manage_campus(actor, institution, section.campus_id):
            raise PermissionDenied("Your role does not cover this campus.")
        _open(section.year)
        for name in ("code", "capacity"):
            if name in data:
                setattr(section, name, data[name])
        class_teacher = (
            _staff(institution, data["class_teacher"], "class_teacher") if data.get("class_teacher") else None
        )
        if Section.objects.filter(year=section.year, code=section.code).exclude(pk=section.pk).exists():
            raise ValidationError({"code": ["Another section this year has this name."]})
        if section.pk and section.capacity < placed(section):
            raise ValidationError({"capacity": [f"{placed(section)} students are already placed here."]})
        section.save()
        if class_teacher is not None:
            _make_class_teacher(actor, section, class_teacher)
        audit.log(
            actor,
            "section.saved",
            section,
            f"Section {section.code} ({section.year.code}) saved",
            institution=institution,
        )
        return section


def _make_class_teacher(actor, section: Section, membership: Membership) -> TeachingAssignment:
    """The class teacher is the section's one whole-class assignment: a new one ends the one before."""
    today = today_for(section.institution)
    current = [row for row in section.teaching.filter(subject__isnull=True) if in_effect(row, today)]
    for row in current:
        if row.membership_id == membership.id:
            return row
        row.ends_on = today - dt.timedelta(days=1)
        row.save(update_fields=["ends_on"])
    return TeachingAssignment.objects.create(
        section=section, subject=None, membership=membership, starts_on=today, created_by=actor
    )


def assign_teacher(actor, section: Section, membership_id, subject_id) -> TeachingAssignment:
    if not can_manage_section(actor, section):
        raise PermissionDenied("Your role does not cover this section's campus.")
    _open(section.year)
    membership = _staff(section.institution, membership_id, "membership")
    subject = None
    if subject_id is not None:
        subject = Subject.objects.filter(pk=subject_id, institution=section.institution, is_active=True).first()
        if subject is None:
            raise ValidationError({"subject": ["Choose an active subject."]})
    if subject is None:
        assignment = _make_class_teacher(actor, section, membership)
    else:
        assignment = TeachingAssignment.objects.create(
            section=section,
            subject=subject,
            membership=membership,
            starts_on=today_for(section.institution),
            created_by=actor,
        )
    what = subject.name if subject else "the class"
    audit.log(
        actor,
        "section.teacher_assigned",
        section,
        f"{membership.user.full_name} teaches {what} in {section.code}",
        institution=section.institution,
    )
    return assignment


def end_teaching(actor, assignment: TeachingAssignment) -> TeachingAssignment:
    section = assignment.section
    if not can_manage_section(actor, section):
        raise PermissionDenied("Your role does not cover this section's campus.")
    # Ends now: the last day it counted was yesterday (an assignment made today then never counts).
    assignment.ends_on = today_for(section.institution) - dt.timedelta(days=1)
    assignment.save(update_fields=["ends_on"])
    audit.log(
        actor,
        "section.teacher_ended",
        section,
        f"{assignment.membership.user.full_name} no longer teaches in {section.code}",
        institution=section.institution,
    )
    return assignment


def in_effect(assignment: TeachingAssignment, today) -> bool:
    return assignment.starts_on <= today and (assignment.ends_on is None or today <= assignment.ends_on)


def section_item(section: Section, viewer) -> dict:
    today = today_for(section.institution)
    rows = list(section.teaching.select_related("membership__user", "subject"))
    teacher = next((row.membership for row in rows if row.subject_id is None and in_effect(row, today)), None)
    return {
        "id": str(section.id),
        "version": section.version,
        "code": section.code,
        "capacity": section.capacity,
        "placed": placed(section),
        "year": {"id": str(section.year_id), "code": section.year.code, "status": section.year.status},
        "grade": {"id": str(section.grade_id), "name": section.grade.name},
        "campus": {"id": str(section.campus_id), "name": section.campus.name},
        "class_teacher": {"id": str(teacher.id), "full_name": teacher.user.full_name} if teacher else None,
        "teachers": [
            {
                "id": str(row.id),
                "membership": {"id": str(row.membership_id), "full_name": row.membership.user.full_name},
                "subject": {"id": str(row.subject_id), "name": row.subject.name} if row.subject_id else None,
                "starts_on": row.starts_on,
                "ends_on": row.ends_on,
                "in_effect": in_effect(row, today),
            }
            for row in rows
        ],
        "can_manage": can_manage_section(viewer, section),
    }
