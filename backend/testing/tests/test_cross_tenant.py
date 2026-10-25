"""Cross-tenant adversarial sweep (BUILD-12): every API route that takes a record id, called by another institution's
admin and by one of its students with this institution's real ids, must refuse, and must change nothing."""

import re
import time
import uuid

import pytest
from django.apps import apps
from django.core.management import call_command
from django.urls import URLResolver, get_resolver

from accounts.models import User
from common.models import AuditEvent
from institutions.models import Institution

UUID_PARAM = re.compile(r"<uuid:(\w+)>")
OTHER_PARAM = re.compile(r"<(?:slug|str|int|path):\w+>|<\w+>")


def _routes():
    def walk(patterns, prefix=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                yield from walk(p.url_patterns, prefix + str(p.pattern))
            else:
                yield prefix + str(p.pattern)

    return sorted({r for r in walk(get_resolver().url_patterns) if r.startswith("api/v1/") and "<uuid:" in r})


def _victim_ids(institution) -> list[uuid.UUID]:
    """One id of every kind of record the institution owns (plus the institution's own id)."""
    ids = [institution.pk]
    for model in apps.get_models():
        names = {f.name for f in model._meta.fields}
        if model._meta.pk.get_internal_type() != "UUIDField" or "institution" not in names:
            continue
        row = model.objects.filter(institution=institution).values_list("pk", flat=True).first()
        if row:
            ids.append(row)
    return ids


@pytest.fixture
def seeded(db, settings):
    settings.DEBUG = True
    call_command("seed_demo", stdout=open("/dev/null", "w"))
    return Institution.objects.get(slug="aster"), Institution.objects.get(slug="meridian")


pytestmark = pytest.mark.adversarial


def test_the_sweep_reaches_real_records_for_their_owner(seeded, client_for):
    """The positive control: the same paths, asked by Aster's own admin, do find Aster's records."""
    aster, _ = seeded
    client = client_for(aster.slug, User.objects.get(username="aster.admin"))
    found = 0
    for route in _routes():
        for victim in _victim_ids(aster):
            response = client.get("/" + OTHER_PARAM.sub("x", UUID_PARAM.sub(str(victim), route)))
            found += response.status_code == 200 and not _harmless(response)
    assert found >= 20  # 23 on the demo data; most ids belong to other routes


@pytest.mark.parametrize("attacker", ["meridian.admin", "student"])
def test_no_route_reaches_another_institutions_records(seeded, client_for, attacker):
    aster, meridian = seeded
    user = (
        User.objects.filter(username=attacker).first()
        or User.objects.filter(memberships__institution=meridian, memberships__kind="student").first()
    )
    assert user is not None
    client = client_for(meridian.slug, user)
    ids, routes = _victim_ids(aster), _routes()
    before = AuditEvent.objects.filter(institution=aster).count()
    leaks, started = [], time.monotonic()
    for route in routes:
        for victim in ids:
            path = "/" + OTHER_PARAM.sub("x", UUID_PARAM.sub(str(victim), route))
            for method in ("get", "post"):
                response = getattr(client, method)(path, {}, format="json") if method == "post" else client.get(path)
                if response.status_code < 400 and not (method == "get" and _harmless(response)):
                    leaks.append(f"{method.upper()} {path} -> {response.status_code}")
    assert leaks == [], "\n".join(leaks[:40])
    assert AuditEvent.objects.filter(institution=aster).count() == before  # nothing was changed at Aster
    assert time.monotonic() - started < 600


def _harmless(response) -> bool:
    """A 2xx that carries none of the victim's data: an empty list or nothing at all."""
    body = response.content.strip()
    return body in (b"", b"[]", b"null", b"{}")
