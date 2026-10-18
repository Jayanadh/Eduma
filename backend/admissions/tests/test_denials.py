"""Every admissions, applicant and student route from the wrong place (slice 4a spec §7, TST-002, TST-033)."""

import datetime as dt

import pytest
from rest_framework.test import APIClient

from accounts.permissions import today_for
from admissions.models import Application, Document
from students.models import Student
from testing import factories

from .conftest import APPS, CYCLES, applicant, switch_on
from .test_applicant import submitted
from .test_enrollment import FIRST
from .test_review import STAFF, act


@pytest.fixture
def ids(world, cycle, client_for):
    family = client_for(world.a.slug, applicant(world.a, "asha.parent"))
    application = submitted(family, cycle).json()
    registrar = client_for(world.a.slug, factories.member(world.a, role="registrar"))
    act(registrar, application, "start-review")
    act(registrar, application, "eligible")
    act(registrar, application, "offer", expires_on=str(today_for(world.a) + dt.timedelta(days=5)))
    mine = family.get(f"{APPS}/{application['id']}").json()
    family.post(f"{APPS}/{application['id']}/accept", {"version": mine["version"]}, format="json")
    act(registrar, application, "enroll", password=FIRST)
    switch_on(world.b)
    return {
        "cycle": cycle["id"],
        "application": application["id"],
        "document": str(Document.objects.filter(application_id=application["id"]).first().id),
        "student": str(Student.objects.get().id),
    }


def staff_routes(ids):
    app = f"{STAFF}/{ids['application']}"
    return [
        ("get", f"{CYCLES}/{ids['cycle']}"),
        ("patch", f"{CYCLES}/{ids['cycle']}"),
        ("post", f"{CYCLES}/{ids['cycle']}/publish"),
        ("post", f"{CYCLES}/{ids['cycle']}/close"),
        ("get", app),
        *[
            ("post", f"{app}/{step}")
            for step in ("start-review", "request-information", "eligible", "reject", "offer", "enroll", "notes")
        ],
        ("get", f"{app}/documents/{ids['document']}"),
        ("post", f"{app}/documents/{ids['document']}/verify"),
        ("post", f"{app}/documents/{ids['document']}/reject"),
        ("get", f"/api/v1/institution/students/{ids['student']}"),
        ("patch", f"/api/v1/institution/students/{ids['student']}"),
    ]


def applicant_routes(ids):
    app = f"{APPS}/{ids['application']}"
    return [
        ("get", app),
        ("patch", app),
        *[("post", f"{app}/{step}") for step in ("submit", "withdraw", "accept", "documents")],
        ("get", f"{app}/documents/{ids['document']}"),
    ]


def call(client, method, url):
    return getattr(client, method)(url, {}, format="json")


def test_platform_host_has_none_of_them(world, ids, client_for):
    client = client_for(None, world.platform_admin)
    for method, url in staff_routes(ids) + applicant_routes(ids):
        assert call(client, method, url).status_code == 404, (method, url)


def test_another_institution_cannot_reach_by_id(world, ids, client_for):
    staff = client_for(world.b.slug, world.b_admin)
    for method, url in staff_routes(ids):
        assert call(staff, method, url).status_code == 404, (method, url)
    stranger = client_for(world.b.slug, applicant(world.b, "birch.parent"))
    for method, url in applicant_routes(ids):
        assert call(stranger, method, url).status_code == 404, (method, url)


def test_signed_out_is_refused(world, ids):
    client = APIClient(HTTP_HOST=f"{world.a.slug}.eduma.test")
    for method, url in staff_routes(ids) + applicant_routes(ids):
        response = call(client, method, url)
        assert response.status_code == 403 and response.json()["code"] == "authentication_required", (method, url)


def test_applicants_cannot_use_staff_routes(world, ids, client_for):
    family = client_for(world.a.slug, Application.objects.get(pk=ids["application"]).owner)
    for method, url in staff_routes(ids):
        assert call(family, method, url).status_code in (403, 404), (method, url)
