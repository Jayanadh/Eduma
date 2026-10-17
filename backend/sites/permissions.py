"""Two kinds of API: platform routes answer only on the Eduma host, institution routes only on an institution's own
host. On the wrong host the route does not exist (404), so neither side learns about the other."""

from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission

from accounts.permissions import has_perm


class PlatformAdmin(BasePermission):
    message = "Only Eduma platform admins can do this."

    def has_permission(self, request, view):
        if request.site_kind != "platform":
            raise NotFound()
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_platform_admin)


class _MemberWith(BasePermission):
    perm = ""
    message = "Your role cannot do this."

    def has_permission(self, request, view):
        if request.site_kind != "institution":
            raise NotFound()
        return has_perm(request.user, request.institution, self.perm)


def member_with(perm: str) -> type[BasePermission]:
    """A permission class for members of the host's institution whose role grants `perm`, e.g. "institution.read"."""
    return type("MemberWith", (_MemberWith,), {"perm": perm})
