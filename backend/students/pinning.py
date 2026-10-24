"""Which program and regulation a college student follows (slice 5b S5B-07): set on enrolling, changed by staff with
student.update, always to a published regulation of the same program."""

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.permissions import has_perm
from common import audit
from common.exceptions import Problem
from students.models import Enrollment, Student


def _label(program, curriculum) -> str | None:
    return f"{program.code} {curriculum}" if curriculum is not None else None


def pin(actor, student: Student, version: int, program, curriculum=None) -> Student:
    from academics.models import CurriculumVersion

    if not has_perm(actor, student.institution, "student.update", student.scope):
        raise PermissionDenied("Your role cannot change this student's program.")
    with transaction.atomic():
        student = Student.objects.select_for_update().select_related("institution").get(pk=student.pk)
        student.check_version(version)
        enrollment = student.enrollments.filter(status=Enrollment.Status.ACTIVE).select_related("program", "curriculum")
        enrollment = enrollment.first()
        if enrollment is None:
            raise Problem(409, "invalid_transition", f"{student.number} is not enrolled now.")
        chosen = None
        if program is not None:
            # The program already followed stays choosable after it is made inactive, like a retired regulation.
            active = Q(is_active=True) | Q(pk=enrollment.program_id)
            chosen = student.institution.programs.filter(active, pk=program).first()
            if chosen is None:
                raise ValidationError({"program": ["Choose an active program."]})
        regulation = None
        if curriculum is not None:
            regulation = CurriculumVersion.objects.filter(pk=curriculum, program=chosen).first()
            if regulation is None:
                raise ValidationError({"curriculum": ["Choose a regulation of this program."]})
            if regulation.pk != enrollment.curriculum_id and regulation.status != CurriculumVersion.Status.PUBLISHED:
                raise ValidationError({"curriculum": ["Choose a published regulation."]})
        changes = {
            "program": {"from": getattr(enrollment.program, "code", None), "to": getattr(chosen, "code", None)},
            "curriculum": {"from": _label(enrollment.program, enrollment.curriculum), "to": _label(chosen, regulation)},
        }
        enrollment.program, enrollment.curriculum = chosen, regulation
        enrollment.save()
        student.save()  # the record's version covers its pin
        if any(change["from"] != change["to"] for change in changes.values()):
            now = changes["curriculum"]["to"] or changes["program"]["to"] or "no program"
            audit.log(actor, "student.program_changed", student, f"{student.number} now follows {now}", changes=changes)
        return student
