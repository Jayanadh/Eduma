"""Whether a module is in use at an institution: in its plan and switched on (slice 3 S3-07). Routes of a module that
is off do not exist (404) for anyone at that institution."""

from django.http import Http404

from configuration.registry import setting


def module_on(institution, key: str) -> bool:
    return institution is not None and key in setting(institution, "modules.enabled")


def require_module(institution, key: str) -> None:
    if not module_on(institution, key):
        raise Http404
