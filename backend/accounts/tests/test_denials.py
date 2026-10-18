"""Every slice 2 route, from the wrong place: the platform host, another institution's host, or signed out."""

import pytest
from rest_framework.test import APIClient

from accounts.models import Membership, RoleAssignment
from testing import factories

BASE = "/api/v1/institution"


@pytest.fixture
def aster(world):
    campus = factories.campus(world.a, code="CITY")
    department = factories.department(world.a, code="SCI", campus=campus)
    role = factories.custom_role(world.a, permissions=["membership.read"])
    person = factories.member(world.a, role="teacher", scope=campus)
    membership = Membership.objects.get(user=person)
    assignment = RoleAssignment.objects.get(membership=membership)
    return {
        "campus": campus.id,
        "department": department.id,
        "role": role.id,
        "staff": membership.id,
        "assignment": assignment.id,
    }


def routes(ids: dict) -> list[tuple[str, str]]:
    staff = f"{BASE}/staff/{ids['staff']}"
    return [
        ("get", f"{BASE}/campuses/{ids['campus']}"),
        ("patch", f"{BASE}/campuses/{ids['campus']}"),
        ("get", f"{BASE}/departments/{ids['department']}"),
        ("patch", f"{BASE}/departments/{ids['department']}"),
        ("get", f"{BASE}/roles/{ids['role']}"),
        ("patch", f"{BASE}/roles/{ids['role']}"),
        ("get", staff),
        ("patch", staff),
        ("post", f"{staff}/assignments"),
        ("post", f"{staff}/assignments/{ids['assignment']}/end"),
        ("post", f"{staff}/password"),
        ("post", f"{staff}/remove"),
        ("post", f"{staff}/restore"),
    ]


LISTS = [("get", f"{BASE}/{name}") for name in ("campuses", "departments", "roles", "permissions", "staff")] + [
    ("post", f"{BASE}/{name}") for name in ("campuses", "departments", "roles", "staff")
]


def call(client: APIClient, method: str, url: str):
    return getattr(client, method)(url, {}, format="json")


def test_platform_host_has_no_institution_routes(world, aster, client_for):
    client = client_for(None, world.platform_admin)
    for method, url in routes(aster) + LISTS:
        assert call(client, method, url).status_code == 404, (method, url)


def test_another_institution_cannot_reach_by_id(world, aster, client_for):
    client = client_for(world.b.slug, world.b_admin)
    for method, url in routes(aster):
        assert call(client, method, url).status_code == 404, (method, url)


def test_signed_out_is_refused(world, aster):
    client = APIClient(HTTP_HOST=f"{world.a.slug}.eduma.test")
    for method, url in routes(aster) + LISTS:
        response = call(client, method, url)
        assert response.status_code == 403, (method, url)
        assert response.json()["code"] == "authentication_required", (method, url)
