"""No route answers 5xx to an empty or odd request (BUILD-12 release gate): every API route, GET and POST with an
empty body, as an institution admin, a student and the platform admin. Run with `pytest -m adversarial`."""

import re
import uuid

import pytest
from django.core.management import call_command
from django.urls import URLResolver, get_resolver

from accounts.models import User
from institutions.models import Institution

pytestmark = pytest.mark.adversarial
PARAM = re.compile(r"<(?:(uuid)|\w+):\w+>|<\w+>")


def _routes():
    def walk(patterns, prefix=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                yield from walk(p.url_patterns, prefix + str(p.pattern))
            else:
                yield prefix + str(p.pattern)

    return sorted({r for r in walk(get_resolver().url_patterns) if r.startswith("api/v1/")})


@pytest.fixture
def seeded(db, settings):
    settings.DEBUG = True
    call_command("seed_demo", stdout=open("/dev/null", "w"))
    return Institution.objects.get(slug="aster")


@pytest.mark.parametrize("who", ["aster.admin", "aster.2027-0001", "eduma.admin"])
def test_no_route_fails_with_a_server_error(seeded, client_for, who):
    client = client_for(None if who == "eduma.admin" else seeded.slug, User.objects.get(username=who))
    broken = []
    for route in _routes():
        path = "/" + PARAM.sub(lambda m: str(uuid.uuid4()) if m.group(1) else "x", route)
        for method in ("get", "post"):
            response = client.post(path, {}, format="json") if method == "post" else client.get(path)
            deliberate = path == "/api/v1/health/ready" and response.status_code == 503  # "not ready" is its job
            if response.status_code >= 500 and not deliberate:
                broken.append(f"{method.upper()} {path} -> {response.status_code}")
    assert broken == [], "\n".join(broken)
