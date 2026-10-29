"""Every module in the catalogue is a real switch: with it off, its pages and endpoints are closed even when the
modules it depends on are on (course registration, affiliations and outcomes were once open with Academics alone)."""

import pytest

from academics.tests import college as setup
from accounts.models import Membership, User
from admissions.tests.conftest import switch_on
from institutions.modules import MODULES

BASE = ("admissions", "students", "academics", "exams")
RESULTS = "/api/v1/institution/results"


@pytest.fixture
def c(world, client_for):
    world.a.category = "college"
    world.a.save()
    c = setup.build(world.a)
    c.student = setup.student(c, "2026-0001", name="Asha Rao")
    login = User.objects.create_user(username="aster.2026-0001", password="x-Long-pass-1", full_name="Asha Rao")
    Membership.objects.create(institution=world.a, user=login, kind="student")
    c.student.user = login
    c.student.save()
    c.admin = client_for(world.a.slug, world.a_admin)
    c.own = client_for(world.a.slug, login)
    return c


def reaches(c, switched_on) -> dict:
    switch_on(c.institution, modules=BASE + switched_on)
    return {
        "staff registration": c.admin.get("/api/v1/institution/academics/windows").status_code,
        "student registration": c.own.get("/api/v1/student/registration").status_code,
        "degree progress": c.own.get("/api/v1/student/progress").status_code,
        "academic record": c.admin.get(f"/api/v1/institution/academics/students/{c.student.id}/progress").status_code,
        "affiliations": c.admin.get("/api/v1/institution/affiliations").status_code,
        "course outcomes": c.admin.get(f"{RESULTS}/courses/{c.courses['MAT101'].id}/outcomes").status_code,
    }


def test_each_module_opens_only_its_own_pages(c):
    closed = reaches(c, ())
    assert set(closed.values()) == {404}, closed
    opened = reaches(c, ("course_registration", "affiliations", "outcomes"))
    assert set(opened.values()) == {200}, opened


def test_every_catalogue_module_is_built():
    assert [key for key, module in MODULES.items() if not module.available] == []
