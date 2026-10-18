from django.db.models import Prefetch
from rest_framework import serializers

from accounts.models import Membership, RoleAssignment
from accounts.permissions import can_manage_person, in_effect, perms_anywhere, today_for


class AssignmentInput(serializers.Serializer):
    role = serializers.CharField(max_length=60)
    scope_type = serializers.ChoiceField(RoleAssignment.ScopeType.choices)
    campus = serializers.UUIDField(required=False, allow_null=True, default=None)
    department = serializers.UUIDField(required=False, allow_null=True, default=None)
    starts_on = serializers.DateField(required=False, allow_null=True, default=None)
    ends_on = serializers.DateField(required=False, allow_null=True, default=None)


class StaffInput(AssignmentInput):
    full_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=40)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    mobile = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class DetailsInput(serializers.Serializer):
    version = serializers.IntegerField()
    full_name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    mobile = serializers.CharField(max_length=20, required=False, allow_blank=True)


def _assignments(membership: Membership):
    return membership.assignments.select_related("custom_role", "campus", "department", "created_by", "institution")


def current_roles(today) -> Prefetch:
    """Prefetches each membership's in-effect assignments into `current_assignments`, for lists."""
    rows = in_effect(RoleAssignment.objects.select_related("custom_role", "campus", "department"), today)
    return Prefetch("assignments", queryset=rows, to_attr="current_assignments")


def roles_of(membership: Membership) -> list[dict]:
    rows = getattr(membership, "current_assignments", None)
    if rows is None:
        rows = in_effect(_assignments(membership), today_for(membership.institution))
    return [{"label": row.role_label, "scope_label": row.scope_label} for row in rows]


def staff_item(membership: Membership) -> dict:
    user = membership.user
    return {
        "id": str(membership.id),
        "full_name": user.full_name,
        "username": user.username,
        "status": membership.status,
        "roles": roles_of(membership),
    }


def phase(row: RoleAssignment, live_ids: set, today) -> str:
    """One of: now; waiting (for approval); later (starts after today); earlier (ended or past). On the institution's
    own calendar."""
    if row.status == RoleAssignment.Status.PENDING:
        return "waiting"
    if row.id in live_ids:
        return "now"
    if row.status == RoleAssignment.Status.ACTIVE and row.starts_on > today:
        return "later"
    return "earlier"


def assignment_item(row: RoleAssignment, live_ids: set, today, viewer) -> dict:
    from accounts.staff import can_decide

    return {
        "id": str(row.id),
        "role_label": row.role_label,
        "scope_type": row.scope_type,
        "scope_label": row.scope_label,
        "starts_on": row.starts_on,
        "ends_on": row.ends_on,
        "status": row.status,
        "end_reason": row.end_reason,
        "in_effect": row.id in live_ids,
        "phase": phase(row, live_ids, today),
        "requested_by_name": row.created_by.full_name if row.created_by else None,
        "can_decide": can_decide(viewer, row),
    }


def staff_detail(membership: Membership, viewer) -> dict:
    user = membership.user
    rows = list(_assignments(membership))
    today = today_for(membership.institution)
    live_ids = set(in_effect(membership.assignments.all(), today).values_list("id", flat=True))
    return {
        **staff_item(membership),
        "email": user.email,
        "mobile": user.mobile,
        "last_login": user.last_login,
        "must_change_password": user.must_change_password,
        "version": membership.version,
        "assignments": [assignment_item(row, live_ids, today, viewer) for row in rows],
        "can_manage": can_manage_person(viewer, membership),
        # The form to give a role: each role and scope is checked against the grant ceiling when it is sent.
        "can_give": membership.status == Membership.Status.ACTIVE
        and membership.user_id != viewer.id
        and "membership.assign" in perms_anywhere(viewer, membership.institution),
    }
