from django.contrib.auth import logout

from accounts.permissions import active_membership
from institutions.models import SIGN_IN_STATES, Institution
from sites.hosts import resolve


class SiteMiddleware:
    """Sets request.site_kind ("platform", "institution" or "unknown"), request.institution (any lifecycle state) and
    request.site_key ("platform", the institution's id, or None), from the host."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        kind, slug = resolve(request.get_host())
        institution = Institution.objects.filter(slug=slug).first() if slug else None
        if kind == "institution" and institution is None:
            kind = "unknown"
        request.site_kind = kind
        request.institution = institution
        request.site_key = "platform" if kind == "platform" else str(institution.id) if institution else None
        return self.get_response(request)


def session_still_valid(request) -> bool:
    """A session belongs to the site it was made on, and lasts only while its user may still sign in there."""
    user = request.user
    if request.session.get("site") != request.site_key or request.site_key is None:
        return False
    if request.site_kind == "platform":
        return user.is_platform_admin
    return request.institution.lifecycle_status in SIGN_IN_STATES and active_membership(user, request.institution)


class SessionSiteMiddleware:
    """Ends a session on its next request when it is used on another host, its institution is suspended or archived,
    its membership is revoked, or a platform admin loses that role. One rule covers replay, suspension and
    revocation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not session_still_valid(request):
            logout(request)
        return self.get_response(request)
