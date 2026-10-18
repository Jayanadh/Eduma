"""Staff of an institution: who the caller may see, and adding a person with a first password and a first role
(slice 2 spec §4.3, §5). Every refusal names the field it is about."""

import uuid

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import CustomRole, Membership, RoleAssignment, User, validate_username
from accounts.permissions import (
    WHOLE,
    Scope,
    active_membership,
    can_assign,
    covers,
    department_tree,
    grants,
    has_perm,
    in_effect,
    today_for,
)
from accounts.roles import BUILTIN_ROLES, PERMISSIONS, institution_only
from common import audit
from common.exceptions import Problem


def own_membership() -> Problem:
    return Problem(403, "own_membership", "Change your own details and password from your profile.")


def resolve_role(institution, role: str) -> tuple[str | None, CustomRole | None, frozenset[str]]:
    """A built-in role key or the id of one of the institution's active custom roles."""
    if role in BUILTIN_ROLES:
        return role, None, BUILTIN_ROLES[role].permissions
    try:
        custom = institution.custom_roles.filter(pk=uuid.UUID(str(role)), is_active=True).first()
    except ValueError:
        custom = None
    if custom is None:
        raise ValidationError({"role": ["Choose one of the institution's roles."]})
    return None, custom, frozenset(custom.permissions)


def resolve_scope(institution, scope_type: str, campus_id, department_id) -> Scope:
    if scope_type == RoleAssignment.ScopeType.CAMPUS:
        if campus_id is None or not institution.campuses.filter(pk=campus_id, is_active=True).exists():
            raise ValidationError({"campus": ["Choose one of the institution's active campuses."]})
        return ("campus", campus_id)
    if scope_type == RoleAssignment.ScopeType.DEPARTMENT:
        if department_id is None or not institution.departments.filter(pk=department_id, is_active=True).exists():
            raise ValidationError({"department": ["Choose one of the institution's active departments."]})
        return ("department", department_id)
    return WHOLE


def check_assignment(actor, institution, data: dict) -> dict:
    """The fields of a new RoleAssignment from validated input, after the grant ceiling: role, scope and dates."""
    role_key, custom, perms = resolve_role(institution, data["role"])
    scope = resolve_scope(institution, data["scope_type"], data.get("campus"), data.get("department"))
    if scope != WHOLE and (whole_only := institution_only(perms)):
        labels = ", ".join(PERMISSIONS[name].label.lower() for name in whole_only)
        raise ValidationError({"scope_type": [f"This role can only be given for the whole institution ({labels})."]})
    starts_on = data.get("starts_on") or today_for(institution)
    ends_on = data.get("ends_on")
    if ends_on is not None and ends_on < starts_on:
        raise ValidationError({"ends_on": ["End the role on or after the day it starts."]})
    if not can_assign(actor, institution, perms, scope):
        raise PermissionDenied("You can't give this role there.")
    return {
        "role_key": role_key or "",
        "custom_role": custom,
        "scope_type": scope[0],
        "campus_id": scope[1] if scope[0] == "campus" else None,
        "department_id": scope[1] if scope[0] == "department" else None,
        "starts_on": starts_on,
        "ends_on": ends_on,
    }


def visible_memberships(actor, institution):
    """Whole-institution readers see everyone, removed people included; others see people with an in-effect role
    inside one of their membership.read scopes."""
    held = grants(active_membership(actor, institution))
    scopes = [where for perms, where in held if "membership.read" in perms]
    everyone = institution.memberships.all()
    if WHOLE in scopes:
        return everyone
    tree = department_tree(institution)
    seen = {
        row.membership_id
        for row in in_effect(RoleAssignment.objects.filter(institution=institution), today_for(institution))
        if any(covers(institution, scope, row.scope, tree) for scope in scopes)
    }
    return everyone.filter(pk__in=seen, status=Membership.Status.ACTIVE)


def create_staff(actor, institution, data: dict) -> Membership:
    """A new login (first password, must change it), its membership and its first role, all or nothing."""
    try:
        username = validate_username(data["username"])
    except DjangoValidationError as error:
        raise ValidationError({"username": error.messages}) from error
    if User.objects.filter(username=username).exists():
        raise ValidationError({"username": ["This login ID is already in use."]})
    assignment = check_assignment(actor, institution, data)
    person = User(
        username=username,
        full_name=data["full_name"],
        email=data.get("email", ""),
        mobile=data.get("mobile", ""),
        must_change_password=True,
        created_by=actor,
    )
    try:
        password_validation.validate_password(data["password"], person)
    except DjangoValidationError as error:
        raise ValidationError({"password": error.messages}) from error
    person.set_password(data["password"])
    with transaction.atomic():
        person.save()
        membership = Membership.objects.create(institution=institution, user=person, created_by=actor)
        row = RoleAssignment.objects.create(
            membership=membership, institution=institution, created_by=actor, **assignment
        )
        audit.log(
            actor,
            "staff.created",
            membership,
            f"Added {person.full_name} as {row.role_label} ({row.scope_label})",
            institution=institution,
            changes={"username": username, "role": row.role_label, "scope": row.scope_label},
        )
    return membership


def _lock(institution) -> None:
    """Staff changes to one institution take turns, so two admins cannot each remove the other at once."""
    type(institution).objects.select_for_update().filter(pk=institution.pk).first()


def check_last_admin(institution, *, losing: RoleAssignment | Membership) -> None:
    """Refuses to take away the last open-ended Institution Admin role of an active person."""
    admins = in_effect(
        RoleAssignment.objects.filter(
            institution=institution,
            role_key="institution_admin",
            scope_type=RoleAssignment.ScopeType.INSTITUTION,
            ends_on__isnull=True,
            membership__status=Membership.Status.ACTIVE,
            membership__user__is_active=True,
        ),
        today_for(institution),
    )
    mine = {"pk": losing.pk} if isinstance(losing, RoleAssignment) else {"membership": losing}
    if admins.filter(**mine).exists() and not admins.exclude(**mine).exists():
        raise Problem(409, "last_admin", "Add another Institution Admin first.")


def give_role(actor, membership: Membership, data: dict) -> RoleAssignment:
    institution = membership.institution
    with transaction.atomic():
        _lock(institution)
        if membership.status != Membership.Status.ACTIVE:
            raise Problem(409, "invalid_transition", "Restore this person before giving them a role.")
        fields = check_assignment(actor, institution, data)
        row = RoleAssignment.objects.create(membership=membership, institution=institution, created_by=actor, **fields)
        audit.log(
            actor,
            "assignment.given",
            membership,
            f"Gave {membership.user.full_name} {row.role_label} ({row.scope_label})",
            institution=institution,
            changes={
                "role": row.role_label,
                "scope": row.scope_label,
                "starts_on": str(row.starts_on),
                "ends_on": str(row.ends_on) if row.ends_on else None,
            },
        )
    return row


def _end(actor, row: RoleAssignment, reason: str) -> None:
    row.status = RoleAssignment.Status.ENDED
    row.ended_by = actor
    row.ended_at = timezone.now()
    row.end_reason = reason
    row.save()


def end_assignment(actor, assignment: RoleAssignment, reason: str) -> RoleAssignment:
    institution = assignment.institution
    with transaction.atomic():
        _lock(institution)
        row = RoleAssignment.objects.select_for_update().get(pk=assignment.pk)
        if row.status != RoleAssignment.Status.ACTIVE:
            raise Problem(409, "invalid_transition", "This role has already ended.")
        if not can_assign(actor, institution, row.permissions, row.scope):
            raise PermissionDenied("You can't end this role: giving it is beyond your own.")
        check_last_admin(institution, losing=row)
        _end(actor, row, reason)
        audit.log(
            actor,
            "assignment.ended",
            row.membership,
            f"Ended {row.membership.user.full_name}'s {row.role_label} ({row.scope_label})",
            institution=institution,
            changes={"reason": reason},
        )
    return row


def reset_password(actor, membership: Membership, password: str) -> None:
    person = membership.user
    try:
        password_validation.validate_password(password, person)
    except DjangoValidationError as error:
        raise ValidationError({"password": error.messages}) from error
    person.set_password(password)
    person.must_change_password = True
    person.save()
    audit.log(
        actor,
        "staff.password_reset",
        membership,
        f"Reset the password of {person.full_name}",
        institution=membership.institution,
    )


def remove(actor, membership: Membership, reason: str, version: int) -> Membership:
    """Ends every role and the membership; the person's sessions end on their next request."""
    institution = membership.institution
    with transaction.atomic():
        _lock(institution)
        membership = Membership.objects.select_for_update().get(pk=membership.pk)
        membership.check_version(version)
        if membership.status != Membership.Status.ACTIVE:
            raise Problem(409, "invalid_transition", "This person has already been removed.")
        check_last_admin(institution, losing=membership)
        for row in membership.assignments.filter(status=RoleAssignment.Status.ACTIVE):
            _end(actor, row, "Removed from staff")
        membership.status = Membership.Status.REVOKED
        membership.save()
        audit.log(
            actor,
            "staff.removed",
            membership,
            f"Removed {membership.user.full_name} from staff",
            institution=institution,
            changes={"reason": reason},
        )
    return membership


def restore(actor, membership: Membership, version: int) -> Membership:
    institution = membership.institution
    if not has_perm(actor, institution, "membership.assign"):
        raise PermissionDenied("Only someone who adds staff for the whole institution can restore a person.")
    with transaction.atomic():
        membership = Membership.objects.select_for_update().get(pk=membership.pk)
        membership.check_version(version)
        if membership.status != Membership.Status.REVOKED:
            raise Problem(409, "invalid_transition", "This person is already on the staff.")
        membership.status = Membership.Status.ACTIVE
        membership.save()
        summary = f"Restored {membership.user.full_name} to staff"
        audit.log(actor, "staff.restored", membership, summary, institution=institution)
    return membership
