"""Student logins: `<institution slug>.<student number>` with a first password (slice 4a S4-07), made at enrollment
or later for a student who has none (slice 4c S4C-12, e.g. after an import)."""

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Membership, User
from accounts.permissions import has_perm
from common import audit
from common.exceptions import Problem
from students.models import Student


def make_login(actor, institution, number: str, full_name: str, password: str) -> User:
    """The login and its student membership. Call inside the caller's transaction."""
    username = f"{institution.slug}.{number}"
    if User.objects.filter(username=username).exists():
        raise Problem(
            409,
            "login_taken",
            f"The student login {username} already belongs to another account. Contact Eduma support to free it.",
        )
    login = User(username=username, full_name=full_name, must_change_password=True, created_by=actor)
    try:
        password_validation.validate_password(password, login)
    except DjangoValidationError as error:
        raise ValidationError({"password": error.messages}) from error
    login.set_password(password)
    login.save()
    Membership.objects.create(institution=institution, user=login, kind=Membership.Kind.STUDENT, created_by=actor)
    return login


def give_login(actor, student: Student, version: int, password: str) -> Student:
    if not has_perm(actor, student.institution, "student.update", student.scope):
        raise PermissionDenied("Your role cannot change this student's sign-in.")
    with transaction.atomic():
        student = Student.objects.select_for_update().select_related("institution", "person").get(pk=student.pk)
        student.check_version(version)
        if student.status != Student.Status.ACTIVE or student.user_id is not None:
            reason = "already has a login" if student.user_id else "has left"
            raise Problem(409, "invalid_transition", f"{student.number} {reason}.")
        student.user = make_login(actor, student.institution, student.number, student.person.full_name, password)
        student.save()
        audit.log(actor, "student.login_created", student, f"Login {student.user.username} made for {student.number}")
        return student
