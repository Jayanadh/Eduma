"""Every API error is an RFC 9457 problem: {type, title, status, detail, code, errors[]} as application/problem+json.
The app reads `code`; `errors` lists field problems as {field: "admin.username", code, message}."""

from django.http import Http404
from rest_framework import exceptions as drf
from rest_framework.response import Response


class Problem(drf.APIException):
    """A refusal with its own status and machine code, e.g. Problem(409, "invalid_transition", "...")."""

    title = "Request refused"

    def __init__(self, status: int, code: str, detail: str, **extra):
        super().__init__(detail, code)
        self.status_code = status
        self.problem_code = code
        self.extra = extra


class VersionConflict(Problem):
    title = "This record changed"

    def __init__(self, current_version: int):
        super().__init__(
            409,
            "version_conflict",
            "Reload the latest record and review your changes.",
            current_version=current_version,
        )


class InvalidTransition(Problem):
    title = "Not allowed in this state"

    def __init__(self, detail: str):
        super().__init__(409, "invalid_transition", detail)


class IdempotencyMismatch(Problem):
    title = "Different request with the same key"

    def __init__(self):
        super().__init__(
            409, "idempotency_mismatch", "This request key was already used for different details. Start again."
        )


# Status, code and title for DRF's own exceptions, most specific first.
_KNOWN = [
    (drf.ParseError, 400, "invalid_request", "Malformed request"),
    (drf.NotAuthenticated, 403, "authentication_required", "Sign-in required"),
    (drf.AuthenticationFailed, 403, "authentication_required", "Sign-in required"),
    (drf.PermissionDenied, 403, "permission_denied", "Not allowed"),
    (drf.NotFound, 404, "not_found", "Not found"),
    (drf.MethodNotAllowed, 405, "method_not_allowed", "Method not allowed"),
    (drf.ValidationError, 422, "validation_failed", "Check the highlighted fields"),
    (drf.Throttled, 429, "rate_limited", "Too many attempts"),
]


def flatten_errors(detail, path: str = "") -> list[dict]:
    """Nested DRF error details as [{field: "a.b.0.c", code, message}]."""
    if isinstance(detail, dict):
        found = []
        for key, value in detail.items():
            name = "" if key in ("non_field_errors", "detail") else str(key)
            found += flatten_errors(value, f"{path}.{name}".strip(".") if name else path)
        return found
    if isinstance(detail, list):
        found = []
        for index, value in enumerate(detail):
            # A list of messages belongs to one field; a list of objects is indexed (items.0.title).
            nested = isinstance(value, (dict, list))
            found += flatten_errors(value, f"{path}.{index}".strip(".") if nested else path)
        return found
    return [{"field": path, "code": getattr(detail, "code", "invalid"), "message": str(detail)}]


def _response(status: int, code: str, title: str, detail: str, errors=(), headers=None, **extra) -> Response:
    body = {
        "type": f"urn:eduma:problem:{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "errors": list(errors),
        **extra,
    }
    return Response(body, status=status, headers=headers, content_type="application/problem+json")


def problem_handler(exc, context):
    if isinstance(exc, Http404):
        exc = drf.NotFound()
    if isinstance(exc, Problem):
        return _response(exc.status_code, exc.problem_code, exc.title, str(exc.detail), **exc.extra)
    for kind, status, code, title in _KNOWN:
        if isinstance(exc, kind):
            errors = flatten_errors(exc.detail) if kind is drf.ValidationError else []
            detail = errors[0]["message"] if errors else str(exc.detail)
            headers = {"Retry-After": str(exc.wait)} if kind is drf.Throttled and exc.wait else None
            return _response(status, code, title, detail, errors, headers)
    return None  # anything else is a bug: Django's 500 handling applies
