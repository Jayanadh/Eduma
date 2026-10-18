"""Who may do what inside an institution, and where (spec pack 02 §2, slice 2 spec §4.3). Permission names are
`<resource>.<action>` from accounts.roles; roles are labels, so code asks these functions, never for a role name.
Platform staff get their authority from is_platform_admin (see sites.permissions.PlatformAdmin), not from here."""

import datetime as dt
import uuid
from zoneinfo import ZoneInfo

from django.db.models import Q, QuerySet
from django.utils import timezone

from accounts.models import Membership, RoleAssignment
from accounts.roles import IMPLICIT

# ("institution", None), ("campus", <campus id>) or ("department", <department id>).
Scope = tuple[str, uuid.UUID | None]
WHOLE: Scope = ("institution", None)
Grants = list[tuple[frozenset[str], Scope]]


def today_for(institution) -> dt.date:
    """Assignments start and end on the institution's own calendar day."""
    return timezone.localdate(timezone=ZoneInfo(institution.timezone))


def in_effect(assignments: QuerySet, today: dt.date) -> QuerySet:
    return assignments.filter(status=RoleAssignment.Status.ACTIVE, starts_on__lte=today).filter(
        Q(ends_on__isnull=True) | Q(ends_on__gte=today)
    )


def live(assignments: QuerySet, today: dt.date) -> QuerySet:
    """In effect now, starting later or waiting for approval: what still relies on a role, campus or department."""
    statuses = (RoleAssignment.Status.ACTIVE, RoleAssignment.Status.PENDING)
    return assignments.filter(status__in=statuses).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))


def active_membership(user, institution) -> Membership | None:
    if user is None or not user.is_authenticated or not user.is_active or institution is None:
        return None
    return Membership.objects.filter(user=user, institution=institution, status=Membership.Status.ACTIVE).first()


def grants(membership: Membership | None) -> Grants:
    """What each of the membership's in-effect assignments allows, and where."""
    if membership is None or membership.status != Membership.Status.ACTIVE or not membership.user.is_active:
        return []
    rows = in_effect(membership.assignments.select_related("custom_role"), today_for(membership.institution))
    return [(row.permissions, row.scope) for row in rows]


def department_tree(institution) -> dict:
    """{department id: (parent id, campus id)} for the whole institution, from one query."""
    rows = institution.departments.values_list("id", "parent_id", "campus_id")
    return {pk: (parent_id, campus_id) for pk, parent_id, campus_id in rows}


def covers(institution, holder: Scope, target: Scope, tree: dict | None = None) -> bool:
    """Whether authority held at `holder` reaches `target` (spec §4.3 scope coverage). Pass `tree` when checking
    many scopes at once."""
    if holder[0] == "institution":
        return True
    if target[0] == "institution":
        return False
    if holder[0] == "campus" and target[0] == "campus":
        return holder[1] == target[1]
    if holder[0] == "department" and target[0] == "campus":
        return False
    tree = department_tree(institution) if tree is None else tree
    if target[1] not in tree:
        return False
    if holder[0] == "campus":
        return tree[target[1]][1] == holder[1]
    node, seen = target[1], set()
    while node is not None and node not in seen:  # `seen`: a loop in bad data must not hang the request
        if node == holder[1]:
            return True
        seen.add(node)
        node = tree.get(node, (None, None))[0]
    return False


def holds(held: Grants, institution, perm: str, scope: Scope) -> bool:
    """Whether grants (from grants()) include `perm` at a scope covering `scope`."""
    return any(perm in perms and covers(institution, where, scope) for perms, where in held)


def has_perm(user, institution, perm: str, scope: Scope = WHOLE) -> bool:
    membership = active_membership(user, institution)
    if membership is None:
        return False
    return perm == IMPLICIT or holds(grants(membership), institution, perm, scope)


def perms_anywhere(user, institution) -> set[str]:
    """Every permission held at some scope: for menus only, since the server checks the scope of each request."""
    membership = active_membership(user, institution)
    if membership is None:
        return set()
    return {IMPLICIT}.union(*(perms for perms, _ in grants(membership)))


def assign_allowed(held: Grants, institution, perms: frozenset[str], scope: Scope) -> bool:
    """can_assign() for grants already loaded."""
    return all(holds(held, institution, perm, scope) for perm in {"membership.assign", *perms})


def can_assign(actor, institution, perms: frozenset[str], scope: Scope) -> bool:
    """The grant ceiling: giving (or ending) a role at a scope needs membership.assign there and every permission the
    role holds, there."""
    return assign_allowed(grants(active_membership(actor, institution)), institution, perms, scope)


def can_manage_person(actor, target: Membership) -> bool:
    """Whether the actor may reset the target's password, change their details or remove them: only if the actor could
    have given every role the target holds or will hold (a role starting tomorrow counts today, or resetting the
    password now would hand over tomorrow's authority). Someone with no role is managed only by a whole-institution
    assigner."""
    if target.user_id == getattr(actor, "id", None):
        return False
    institution = target.institution
    held = grants(active_membership(actor, institution))
    roles = list(live(target.assignments.select_related("custom_role"), today_for(institution)))
    if not roles and not holds(held, institution, "membership.assign", WHOLE):
        return False
    return all(assign_allowed(held, institution, row.permissions, row.scope) for row in roles)
