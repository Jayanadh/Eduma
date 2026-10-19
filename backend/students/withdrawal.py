"""A student leaving, and the undo for a mistaken withdrawal (slice 4b S4B-09). Nothing is deleted: the enrollment
ends with its date and reason, the student's login stops, and fees are left to the Fees module."""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Membership
from accounts.permissions import has_perm, today_for
from common import audit
from common.exceptions import Problem
from students.models import Enrollment, Student

UPDATE = "student.update"


def _locked(actor, student: Student, version: int) -> Student:
    if not has_perm(actor, student.institution, UPDATE, student.scope):
        raise PermissionDenied("Your role cannot withdraw or reinstate this student.")
    student = Student.objects.select_for_update().select_related("institution").get(pk=student.pk)
    student.check_version(version)
    return student


def _login(student: Student, status: str) -> None:
    membership = Membership.objects.filter(institution=student.institution, user=student.user_id).first()
    if membership is not None:
        membership.status = status
        membership.save()  # a revoked membership ends the student's sessions on their next request


def withdraw(actor, student: Student, version: int, effective_on, reason: str, clearance_note: str = "") -> Student:
    reason = reason.strip()
    if not reason:
        raise ValidationError({"reason": ["Say why the student is leaving."]})
    with transaction.atomic():
        student = _locked(actor, student, version)
        if student.status != Student.Status.ACTIVE:
            raise Problem(409, "invalid_transition", f"{student.number} has already left.")
        if effective_on > today_for(student.institution):
            raise ValidationError({"effective_on": ["Withdrawal can't be scheduled yet; record it on the day."]})
        enrollment = student.enrollments.filter(status=Enrollment.Status.ACTIVE).first()
        if enrollment is not None and effective_on < enrollment.entry_date:
            raise ValidationError({"effective_on": ["That is before the enrollment starts."]})
        if enrollment is not None:
            enrollment.status = Enrollment.Status.ENDED
            enrollment.exit_date, enrollment.exit_reason = effective_on, reason
            enrollment.save()
        student.status, student.left_on = Student.Status.WITHDRAWN, effective_on
        student.save()
        _login(student, Membership.Status.REVOKED)
        changes = {"effective_on": str(effective_on), "reason": reason, "clearance_note": clearance_note.strip()}
        audit.log(
            actor, "student.withdrawn", student, f"{student.number} withdrawn from {effective_on}", changes=changes
        )
        return student


def can_reinstate(student: Student) -> bool:
    latest = student.enrollments.order_by("-entry_date", "-created_at").first()
    return (
        student.status == Student.Status.WITHDRAWN and latest is not None and latest.status == Enrollment.Status.ENDED
    )


def reinstate(actor, student: Student, version: int) -> Student:
    with transaction.atomic():
        student = _locked(actor, student, version)
        if not can_reinstate(student):
            raise Problem(409, "invalid_transition", f"{student.number} is not withdrawn.")
        latest = student.enrollments.order_by("-entry_date", "-created_at").first()
        latest.status, latest.exit_date, latest.exit_reason = Enrollment.Status.ACTIVE, None, ""
        latest.save()
        student.status, student.left_on = Student.Status.ACTIVE, None
        student.save()
        _login(student, Membership.Status.ACTIVE)
        audit.log(actor, "student.reinstated", student, f"{student.number} reinstated")
        return student
