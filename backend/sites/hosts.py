"""Which site a request is for, from its host: the Eduma main site at the base host (EDUMA_BASE_URL), or an
institution at <slug>.<base host> or at its custom domain. Hosts are case-insensitive and the port is ignored."""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError

from institutions.models import validate_slug


def _base() -> tuple[str, str, int | None]:
    parts = urlsplit(settings.EDUMA_BASE_URL)
    return parts.scheme, (parts.hostname or "").lower(), parts.port


def host_name(host: str) -> str:
    return host.lower().split(":")[0]


def resolve(host: str) -> tuple[str, str | None]:
    """("platform", None), ("institution", slug) or ("unknown", None); an unknown host may be a custom domain."""
    name = host_name(host)
    _, base_host, _ = _base()
    if name == base_host:
        return "platform", None
    label, dot, rest = name.partition(".")
    if dot and rest == base_host:
        try:
            return "institution", validate_slug(label)
        except ValidationError:
            pass
    return "unknown", None


def _url(host: str) -> str:
    scheme, _, port = _base()
    return f"{scheme}://{host}" + (f":{port}" if port else "")


def platform_url() -> str:
    return _url(_base()[1])


def institution_url(institution) -> str:
    """Its custom domain when it has one, else <slug>.<base host>; same scheme and port as the base."""
    return _url(institution.custom_domain or f"{institution.slug}.{_base()[1]}")
