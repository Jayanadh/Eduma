"""Built-in and custom roles, and the permission registry, for an institution's own admins (slice 2 spec §4–5)."""

from collections import Counter

from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from accounts.models import CustomRole, Membership, RoleAssignment
from accounts.permissions import (
    WHOLE,
    active_membership,
    assign_allowed,
    grants,
    holds,
    live,
    perms_anywhere,
    today_for,
)
from accounts.role_serializers import CustomRoleInput
from accounts.roles import BUILTIN_ROLES, IMPLICIT, PERMISSIONS, institution_only, powerful
from common import audit
from common.exceptions import Problem
from common.pagination import Pages
from configuration.registry import setting
from sites.permissions import member_with


def holds_any(*perms: str) -> type[BasePermission]:
    """Members holding any of `perms` at some scope (lists that each row then filters by scope)."""

    class HoldsAny(BasePermission):
        message = "Your role cannot do this."

        def has_permission(self, request, view):
            if request.site_kind != "institution":
                raise NotFound()
            return bool(perms_anywhere(request.user, request.institution) & set(perms))

    return HoldsAny


def permission_groups() -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for p in PERMISSIONS.values():
        groups.setdefault(p.group, []).append(
            {"name": p.name, "label": p.label, "institution_only": p.institution_only}
        )
    return [{"group": name, "permissions": items} for name, items in groups.items()]


class PermissionsView(GenericAPIView):
    permission_classes = [holds_any("role.manage", "membership.read", "membership.assign")]

    def get(self, request):
        return Response(permission_groups())


def _counts(institution) -> Counter:
    rows = live(
        RoleAssignment.objects.filter(institution=institution, membership__status=Membership.Status.ACTIVE),
        today_for(institution),
    ).values_list("role_key", "custom_role_id")
    return Counter(str(custom) if custom else key for key, custom in rows)


def role_item(role: CustomRole, counts: Counter) -> dict:
    return {
        "id": str(role.id),
        "builtin": False,
        "label": role.name,
        "description": role.description,
        "permissions": sorted(role.permissions),
        "assigned_count": counts[str(role.id)],
        "is_active": role.is_active,
        "version": role.version,
    }


def builtin_items(counts: Counter) -> list[dict]:
    return [
        {
            "id": role.key,
            "builtin": True,
            "label": role.label,
            "description": role.description,
            "permissions": sorted(role.permissions),
            "assigned_count": counts[role.key],
            "is_active": True,
            "version": None,
        }
        for role in BUILTIN_ROLES.values()
    ]


def assignable_somewhere(held, institution, perms: frozenset[str]) -> bool:
    """Whether the holder of `held` could give a role with `perms` at any scope where they may assign."""
    scopes = [where for p, where in held if "membership.assign" in p]
    if institution_only(perms):
        scopes = [WHOLE] if scopes else []
    return any(assign_allowed(held, institution, perms, scope) for scope in scopes)


def _check_permissions(actor, institution, names: list[str]) -> list[str]:
    chosen = sorted(set(names))
    for name in chosen:
        if name == IMPLICIT:
            raise ValidationError({"permissions": ["Everyone in the institution can already see its home."]})
        if name not in PERMISSIONS:
            raise ValidationError({"permissions": [f"Unknown permission: {name}."]})
    held = grants(active_membership(actor, institution))
    if not all(holds(held, institution, name, WHOLE) for name in chosen):
        raise ValidationError({"permissions": ["You can only give permissions you hold yourself."]})
    return chosen


def _check_name(institution, name: str, role: CustomRole | None) -> str:
    name = name.strip()
    clash = CustomRole.objects.filter(institution=institution, is_active=True, name__iexact=name)
    if role is not None:
        clash = clash.exclude(pk=role.pk)
    if clash.exists():
        raise ValidationError({"name": ["Another role already has this name."]})
    return name


class RoleList(GenericAPIView):
    """GET: built-in roles, then the institution's custom roles (?assignable=1: only those the caller could give).
    POST: a new custom role."""

    pagination_class = Pages

    def get_permissions(self):
        if self.request.method == "GET":
            return [holds_any("membership.read", "role.manage", "membership.assign")()]
        return [member_with("role.manage")()]

    def get(self, request):
        institution = request.institution
        counts = _counts(institution)
        items = builtin_items(counts) + [role_item(r, counts) for r in institution.custom_roles.all()]
        if len(search := request.query_params.get("search", "").strip()) >= 3:
            items = [item for item in items if search.lower() in item["label"].lower()]
        if request.query_params.get("assignable") == "1":
            held = grants(active_membership(request.user, institution))
            items = [
                item
                for item in items
                if item["is_active"] and assignable_somewhere(held, institution, frozenset(item["permissions"]))
            ]
        return self.get_paginated_response(self.paginate_queryset(items))

    def post(self, request):
        data = CustomRoleInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        institution = request.institution
        with transaction.atomic():
            role = CustomRole.objects.create(
                institution=institution,
                name=_check_name(institution, values["name"], None),
                description=values["description"],
                permissions=_check_permissions(request.user, institution, values["permissions"]),
                created_by=request.user,
            )
            summary = f"Created role {role.name}"
            audit.log(request.user, "role.created", role, summary, changes={"permissions": role.permissions})
        return Response(role_item(role, Counter()), status=status.HTTP_201_CREATED)


class RoleDetail(GenericAPIView):
    permission_classes = [member_with("role.manage")]

    def role(self) -> CustomRole:
        role = self.request.institution.custom_roles.filter(pk=self.kwargs["pk"]).first()
        if role is None:
            raise NotFound()
        return role

    def get(self, request, pk):
        return Response(role_item(self.role(), _counts(request.institution)))

    def patch(self, request, pk):
        found = self.role()
        data = CustomRoleInput(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        changes = dict(data.validated_data)
        institution = request.institution
        with transaction.atomic():
            role = CustomRole.objects.select_for_update().get(pk=found.pk)
            role.check_version(changes.pop("version", None))
            held = grants(active_membership(request.user, institution))
            if not all(holds(held, institution, name, WHOLE) for name in role.permissions):
                raise PermissionDenied("This role includes permissions you don't hold.")
            if "name" in changes or (changes.get("is_active") and not role.is_active):
                changes["name"] = _check_name(institution, changes.get("name", role.name), role)
            in_use = live(role.assignments.all(), today_for(institution))
            if "permissions" in changes:
                changes["permissions"] = _check_permissions(request.user, institution, changes["permissions"])
                narrow = in_use.exclude(scope_type=RoleAssignment.ScopeType.INSTITUTION).count()
                if narrow and (whole_only := institution_only(changes["permissions"])):
                    who = "1 person has" if narrow == 1 else f"{narrow} people have"
                    labels = ", ".join(PERMISSIONS[name].label.lower() for name in whole_only)
                    message = f"{who} this role at a campus or department; {labels} can only be given for the whole"
                    raise ValidationError({"permissions": [f"{message} institution."]})
                gained = set(changes["permissions"]) - set(role.permissions)
                held = in_use.count()
                if (
                    gained
                    and held
                    and powerful(changes["permissions"])
                    and setting(institution, "access.role_approval")
                ):
                    raise Problem(
                        409,
                        "needs_approval",
                        f"{held} {'person holds' if held == 1 else 'people hold'} this role. While approval for "
                        "powerful roles is on, a held role cannot gain powers: make a new role and give it, so each "
                        "new power is approved.",
                    )
            if changes.get("is_active") is False and role.is_active and in_use.exists():
                raise Problem(409, "in_use", "Take this role away from everyone who has it first.")
            diff = {
                name: {"from": getattr(role, name), "to": value}
                for name, value in changes.items()
                if getattr(role, name) != value
            }
            for name, value in changes.items():
                setattr(role, name, value)
            role.save()
            if diff:
                archived = diff.get("is_active", {}).get("to") is False
                action, verb = ("role.archived", "Archived") if archived else ("role.updated", "Changed")
                audit.log(request.user, action, role, f"{verb} role {role.name}", changes=diff)
        return Response(role_item(role, _counts(institution)))
