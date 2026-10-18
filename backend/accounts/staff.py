"""Staff of an institution: who the caller may see, and adding a person with a first password and a first role
(slice 2 spec §4.3, §5). Every refusal names the field it is about."""

import uuid

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
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
