"""Programs and courses (slice 5b S5B-01, S5B-03, S5B-08): managed with academic_structure.manage at their
department, or for the whole institution when they have none."""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.models import Course, Program
from academics.structure import MANAGE
from accounts.permissions import WHOLE, Scope, has_perm
from common import audit


def department_scope(department_id) -> Scope:
    return ("department", department_id) if department_id else WHOLE


def can_manage(actor, row) -> bool:
    return has_perm(actor, row.institution, MANAGE, department_scope(row.department_id))


def _require(actor, row) -> None:
    if not can_manage(actor, row):
        what = "this department" if row.department_id else "the whole institution"
        raise PermissionDenied(f"Your role does not cover {what}.")


def _save(actor, institution, row, data: dict, version: int | None, fields: tuple, what: str):
    with transaction.atomic():
        if not row._state.adding:
            row = type(row).objects.select_for_update().get(pk=row.pk)
            row.check_version(version)
            _require(actor, row)  # where it is now, and below where it is going
        if "department" in data:
            row.department = None
            if data["department"] is not None:
                row.department = institution.departments.filter(pk=data["department"], is_active=True).first()
                if row.department is None:
                    raise ValidationError({"department": ["Choose an active department."]})
        _require(actor, row)
        for name in fields:
            if name in data:
                setattr(row, name, data[name])
        if type(row).objects.filter(institution=institution, code=row.code).exclude(pk=row.pk).exists():
            raise ValidationError({"code": [f"Another {what} has this code."]})
        row.save()
        audit.log(actor, f"{what}.saved", row, f"{what.capitalize()} {row.code} saved", institution=institution)
        return row


def save_program(actor, institution, program: Program | None, data: dict, version: int | None = None) -> Program:
    fields = ("code", "name", "qualification", "length_terms", "is_active")
    return _save(actor, institution, program or Program(institution=institution), data, version, fields, "program")


def save_course(actor, institution, course: Course | None, data: dict, version: int | None = None) -> Course:
    fields = ("code", "title", "credits", "kind", "is_active")
    return _save(actor, institution, course or Course(institution=institution), data, version, fields, "course")


def _department(row) -> dict | None:
    return {"id": str(row.department_id), "name": row.department.name} if row.department_id else None


def program_item(program: Program, viewer) -> dict:
    return {
        "id": str(program.id),
        "version": program.version,
        "code": program.code,
        "name": program.name,
        "qualification": program.qualification,
        "length_terms": program.length_terms,
        "department": _department(program),
        "is_active": program.is_active,
        "can_manage": can_manage(viewer, program),
    }


def course_item(course: Course, viewer) -> dict:
    return {
        "id": str(course.id),
        "version": course.version,
        "code": course.code,
        "title": course.title,
        "credits": str(course.credits),
        "kind": course.kind,
        "kind_label": course.get_kind_display(),
        "department": _department(course),
        "is_active": course.is_active,
        "can_manage": can_manage(viewer, course),
    }
