import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from testing import factories


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Login throttling counts live in the cache, so every test starts from zero."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def client_for():
    """client_for(slug, user) -> an API client on that institution's host (slug None: the platform host), signed in as
    user via force_authenticate. Tests of real sessions build their own client and sign in through the API."""

    def make(slug: str | None, user=None) -> APIClient:
        client = APIClient(HTTP_HOST="eduma.test" if slug is None else f"{slug}.eduma.test")
        if user is not None:
            client.force_authenticate(user)
        return client

    return make


@pytest.fixture
def world(db):
    """A platform admin and two active institutions, a and b, each with its Institution Admin (a_admin, b_admin)."""

    class World:
        pass

    result = World()
    result.platform_admin = factories.platform_admin(username="eduma.admin")
    result.a = factories.institution(slug="aster", display_name="Aster School")
    result.b = factories.institution(slug="birch", display_name="Birch College", category="college")
    result.a_admin = factories.member(result.a, username="aster.admin")
    result.b_admin = factories.member(result.b, username="birch.admin")
    return result
