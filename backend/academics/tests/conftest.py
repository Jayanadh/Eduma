import pytest

from admissions.tests.conftest import switch_on

API = "/api/v1/institution/academics"


@pytest.fixture
def on(world):
    switch_on(world.a, modules=("admissions", "students", "academics"))
    return world.a


@pytest.fixture
def admin(world, on, client_for):
    return client_for(world.a.slug, world.a_admin)


def make_year(client, code="2026–27", start="2026-06-01", end="2027-03-31", **extra):
    return client.post(f"{API}/years", {"code": code, "starts_on": start, "ends_on": end, **extra}, format="json")
