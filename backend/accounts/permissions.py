"""Who may do what inside an institution. Permission names are `<resource>.<action>` from the spec pack (02); roles
are labels, so code checks permissions, never role names. Platform staff get their authority from is_platform_admin
(see sites.permissions.PlatformAdmin), not from this table."""

from accounts.models import Membership, Role

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Role.INSTITUTION_ADMIN: frozenset({"institution.read", "institution_profile.update", "institution_brand.update"}),
}


def active_membership(user, institution) -> Membership | None:
    if user is None or not user.is_authenticated or not user.is_active or institution is None:
        return None
    return Membership.objects.filter(user=user, institution=institution, status=Membership.Status.ACTIVE).first()


def has_perm(user, institution, perm: str) -> bool:
    membership = active_membership(user, institution)
    return membership is not None and perm in ROLE_PERMISSIONS.get(membership.role, frozenset())
