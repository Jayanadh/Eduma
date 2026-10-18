from django.contrib.auth import logout
from django.http import JsonResponse

from accounts.permissions import active_membership
from institutions.models import SIGN_IN_STATES, Institution, LifecycleStatus
from sites.hosts import host_name, resolve


class SiteMiddleware:
    """Sets request.site_kind ("platform", "institution" or "unknown"), request.institution (any lifecycle state) and
    request.site_key ("platform", the institution's id, or None), from the host: the base host, <slug>.<base host> or
    an institution's custom domain."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        kind, slug = resolve(host)
        institution = None
        if kind == "institution":
            institution = Institution.objects.filter(slug=slug).first()
        elif kind == "unknown":
            institution = Institution.objects.filter(custom_domain=host_name(host)).first()
        kind = "platform" if kind == "platform" else "institution" if institution else "unknown"
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


# What a member of a restricted institution may still post: signing in and out, and changing their own password.
OPEN_WHILE_RESTRICTED = ("/api/v1/session/login", "/api/v1/session/logout", "/api/v1/session/change-password")
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


class RestrictedMiddleware:
    """A restricted institution is read-only on its own host: every change is refused with the platform's reason,
    whatever view it reaches (spec S2-10). The platform host is unaffected."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        institution = request.institution
        if (
            request.site_kind == "institution"
            and institution.lifecycle_status == LifecycleStatus.RESTRICTED
            and request.method not in SAFE_METHODS
            and request.path not in OPEN_WHILE_RESTRICTED
        ):
            body = {
                "type": "urn:eduma:problem:institution_restricted",
                "title": "Read-only for now",
                "status": 403,
                "detail": f"{institution.display_name} is read-only for now: {institution.status_reason}",
                "code": "institution_restricted",
                "errors": [],
            }
            return JsonResponse(body, status=403, content_type="application/problem+json")
        return self.get_response(request)
