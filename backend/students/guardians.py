"""Guardian links (slice 4b §2): proposed by enrollment or by staff, never inferred from matching names or phones;
verified or revoked by staff with guardian_link.manage. Audit lines go on the student, without notes or evidence."""

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Membership, User, validate_username
from accounts.permissions import has_perm, today_for
from common import audit
from common.exceptions import Problem
from students.models import GuardianLink, Person, Student

MANAGE = "guardian_link.manage"


def log_link(actor, link: GuardianLink, action: str, summary: str):
    changes = {
        "link": str(link.id),
        "adult": link.adult.full_name,
        "relationship": link.relationship,
        "status": link.status,
    }
    return audit.log(actor, action, link.student, summary, institution=link.student.institution, changes=changes)


def _new(actor, student: Student, adult: Person, relationship: str, source: str, user=None) -> GuardianLink:
    link = GuardianLink.objects.create(
        institution=student.institution,
        student=student,
        adult=adult,
        user=user,
        relationship=relationship,
        source=source,
        proposed_by=actor,
    )
    log_link(
        actor, link, "student.guardian_proposed", f"{adult.full_name} proposed as {relationship} of {student.number}"
    )
    return link


def propose_from_application(actor, student: Student, application) -> GuardianLink:
    """The adult who applied, waiting for staff to check their authority. Call inside enrollment's transaction."""
    existing = student.guardian_links.filter(user=application.owner).exclude(status=GuardianLink.Status.REVOKED)
    if (found := existing.first()) is not None:
        return found
    adult = Person.objects.create(
        institution=student.institution,
        full_name=application.guardian_name,
        phone=application.guardian_phone,
        email=application.guardian_email,
        address=application.address,
    )
    relationship = application.guardian_relationship
    return _new(actor, student, adult, relationship, GuardianLink.Source.ENROLLMENT, user=application.owner)


def propose(actor, student: Student, adult: dict, relationship: str) -> GuardianLink:
    """Another adult named by staff; no login until verification makes one."""
    person = Person.objects.create(
        institution=student.institution,
        full_name=adult["full_name"],
        phone=adult.get("phone", ""),
        email=adult.get("email", ""),
    )
    return _new(actor, student, person, relationship, GuardianLink.Source.STAFF)


def is_adult(date_of_birth, today) -> bool:
    if date_of_birth is None:
        return False
    before_birthday = (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - before_birthday >= 18


def needs_adult_review(link: GuardianLink, today) -> bool:
    """Verified for a child who has since turned 18, on a basis other than the student's own consent."""
    born = link.student.person.date_of_birth
    if link.status != GuardianLink.Status.ACTIVE or not is_adult(born, today) or link.verified_at is None:
        return False
    verified = link.verified_at.date()
    return not is_adult(born, verified) and link.authority_basis != GuardianLink.Basis.STUDENT_CONSENT


def can_manage_links(actor, student: Student) -> bool:
    return has_perm(actor, student.institution, MANAGE, student.scope)


def _locked(link: GuardianLink, version: int) -> GuardianLink:
    link = (
        GuardianLink.objects.select_for_update(of=("self",))
        .select_related("student__person", "adult", "user")
        .get(pk=link.pk)
    )
    link.check_version(version)
    return link


def _login(link: GuardianLink, actor, login: dict | None):
    """The adult's login: the one they have, a new one, or none. Field errors name `login.*`."""
    if link.user is not None or not login:
        return link.user
    try:
        username = validate_username(login["username"])
    except DjangoValidationError as error:
        raise ValidationError({"login.username": error.messages}) from error
    if User.objects.filter(username=username).exists():
        raise ValidationError({"login.username": ["This login ID is already in use. Choose another."]})
    user = User(username=username, full_name=link.adult.full_name, email=link.adult.email, must_change_password=True)
    user.created_by = actor
    try:
        password_validation.validate_password(login["password"], user)
    except DjangoValidationError as error:
        raise ValidationError({"login.password": error.messages}) from error
    user.set_password(login["password"])
    user.save()
    return user


def _family_membership(user, institution) -> None:
    """A verified adult's login becomes the institution's guardian; staff and student logins cannot be one."""
    membership = Membership.objects.select_for_update().filter(institution=institution, user=user).first()
    if membership is None:
        Membership.objects.create(institution=institution, user=user, kind=Membership.Kind.GUARDIAN)
        return
    if membership.kind in (Membership.Kind.STAFF, Membership.Kind.STUDENT):
        raise Problem(
            409,
            "kind_conflict",
            f"{user.username} is a {membership.get_kind_display().lower()} login here. Give this guardian a login "
            "of their own.",
        )
    membership.kind = Membership.Kind.GUARDIAN
    membership.status = Membership.Status.ACTIVE
    membership.save()


def verify(actor, link: GuardianLink, version: int, data: dict) -> GuardianLink:
    student = link.student
    today = today_for(student.institution)
    with transaction.atomic():
        link = _locked(link, version)
        if link.status != GuardianLink.Status.PROPOSED:
            raise Problem(409, "invalid_transition", f"This link is {link.get_status_display().lower()}.")
        if link.student.status != Student.Status.ACTIVE:
            raise Problem(409, "invalid_transition", f"{link.student.number} has left; links cannot be verified.")
        starts_on = data.get("starts_on") or today
        if data.get("ends_on") and data["ends_on"] < starts_on:
            raise ValidationError({"ends_on": ["End on or after the start date."]})
        basis = data["authority_basis"]
        if is_adult(link.student.person.date_of_birth, today) and basis != GuardianLink.Basis.STUDENT_CONSENT:
            raise ValidationError(
                {"authority_basis": ["This student is an adult: only their own consent can give another adult access."]}
            )
        user = _login(link, actor, data.get("login"))
        if user is not None:
            _family_membership(user, student.institution)
        access = data.get("access") or {}
        link.user = user
        link.status = GuardianLink.Status.ACTIVE
        link.authority_basis = basis
        link.verification_method = data["verification_method"]
        link.verification_reference = data.get("verification_reference", "")
        link.restrictions = data.get("restrictions", "")
        link.starts_on, link.ends_on = starts_on, data.get("ends_on")
        link.access_record = access.get("record", True)
        link.access_fees = access.get("fees", False)
        link.access_messages = access.get("messages", False)
        link.verified_by, link.verified_at = actor, timezone.now()
        link.save()
        login = f" with login {user.username}" if user is not None else ""
        log_link(actor, link, "student.guardian_verified", f"{link.adult.full_name} verified{login}")
        return link


def revoke(actor, link: GuardianLink, version: int, reason: str) -> GuardianLink:
    reason = reason.strip()
    if not reason:
        raise ValidationError({"reason": ["Say why, for the record."]})
    with transaction.atomic():
        link = _locked(link, version)
        if link.status == GuardianLink.Status.REVOKED:
            raise Problem(409, "invalid_transition", "This link is already revoked.")
        link.status = GuardianLink.Status.REVOKED
        link.revoked_by, link.revoked_at, link.revoke_reason = actor, timezone.now(), reason
        link.save()
        log_link(actor, link, "student.guardian_revoked", f"{link.adult.full_name}'s link revoked")
        return link
