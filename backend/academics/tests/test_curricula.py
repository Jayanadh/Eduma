"""Curriculum versions (slice 5b S5B-02, S5B-04; spec §7.1–2, Review Focus 1, 2 and 5)."""

from types import SimpleNamespace

import pytest

from academics.models import Course, Program
from testing import factories

from .conftest import API


@pytest.fixture
def college(world, on):
    physics = factories.department(world.a, code="PHY", name="Physics")
    found = SimpleNamespace(physics=physics, chemistry=factories.department(world.a, code="CHE", name="Chemistry"))
    found.program = Program.objects.create(
        institution=world.a, code="BSC-PHY", name="B.Sc Physics", qualification="B.Sc", department=physics,
        length_terms=6,
    )  # fmt: skip
    for code, credits, kind in (("PHY101", 4, "theory"), ("PHY101L", 1, "lab"), ("MAT101", 4, "theory"),
                                ("PHY201", 4, "theory")):  # fmt: skip
        setattr(
            found, code, Course.objects.create(institution=world.a, code=code, title=code, credits=credits, kind=kind)
        )
    return found


def draft(client, college, **changes):
    body = {"regulation": "R2026", "cohort": 2026, "credits_required": "120", **changes}
    return client.post(f"{API}/programs/{college.program.id}/curricula", body, format="json")


def add(client, curriculum, course, term=1, prerequisites=(), **changes):
    body = {"course": str(course.id), "category": "core", "term": term,
            "prerequisites": [str(p.id) for p in prerequisites], **changes}  # fmt: skip
    return client.post(f"{API}/curricula/{curriculum['id']}/courses", body, format="json")


def entry(curriculum, code):
    return next(c for term in curriculum["terms"] for c in term["courses"] if c["course"]["code"] == code)


def act(client, curriculum, action):
    return client.post(
        f"{API}/curricula/{curriculum['id']}/{action}", {"version": curriculum["version"]}, format="json"
    )


def fields(response):
    return [e["field"] for e in response.json()["errors"]]


@pytest.fixture
def published(admin, college):
    made = draft(admin, college).json()
    add(admin, made, college.PHY101)
    add(admin, made, college.MAT101)
    shown = add(admin, made, college.PHY201, term=3, prerequisites=[college.PHY101]).json()
    return act(admin, shown, "publish").json()


def test_draft_groups_courses_by_term(admin, college):
    made = draft(admin, college)
    assert made.status_code == 201, made.json()
    assert made.json()["revision"] == 1 and made.json()["status"] == "draft"
    assert fields(draft(admin, college)) == ["regulation"]
    add(admin, made.json(), college.PHY101)
    shown = add(admin, made.json(), college.PHY201, term=3, prerequisites=[college.PHY101]).json()
    assert [term["term"] for term in shown["terms"]] == [1, 3]
    assert entry(shown, "PHY201")["prerequisites"] == ["PHY101"]
    assert shown["total_credits"] == "8.0"
    assert fields(add(admin, shown, college.PHY101)) == ["course"]
    listed = admin.get(f"{API}/programs/{college.program.id}/curricula").json()
    assert [row["regulation"] for row in listed] == ["R2026"]


def test_prerequisite_rules(admin, college):
    made = draft(admin, college).json()
    assert fields(add(admin, made, college.PHY201, prerequisites=[college.PHY101])) == ["prerequisites"]
    assert fields(add(admin, made, college.PHY101, term=7)) == ["term"]
    a = add(admin, made, college.PHY101).json()
    b = add(admin, made, college.MAT101, prerequisites=[college.PHY101]).json()
    c = add(admin, made, college.PHY201, prerequisites=[college.MAT101]).json()
    url = f"{API}/curricula/{made['id']}/courses/{entry(c, 'PHY101')['id']}"
    assert fields(admin.patch(url, {"prerequisites": [str(college.PHY101.id)]}, format="json")) == ["prerequisites"]
    closing = admin.patch(url, {"prerequisites": [str(college.PHY201.id)]}, format="json")
    assert closing.status_code == 422 and fields(closing) == ["prerequisites"]
    assert entry(admin.get(f"{API}/curricula/{made['id']}").json(), "PHY101")["prerequisites"] == []
    used = admin.delete(f"{API}/curricula/{made['id']}/courses/{entry(b, 'MAT101')['id']}")
    assert used.status_code == 409 and used.json()["code"] == "in_use"
    assert admin.delete(f"{API}/curricula/{made['id']}/courses/{entry(c, 'PHY201')['id']}").status_code == 200
    assert a


def test_publish_freezes(admin, college, published):
    empty = draft(admin, college, regulation="R2027").json()
    assert act(admin, empty, "publish").status_code == 422
    assert published["status"] == "published" and published["published_at"]
    patched = admin.patch(
        f"{API}/curricula/{published['id']}", {"version": published["version"], "cohort": 2027}, format="json"
    )
    assert patched.status_code == 409 and patched.json()["code"] == "published"
    assert add(admin, published, college.PHY101L).json()["code"] == "published"
    url = f"{API}/curricula/{published['id']}/courses/{entry(published, 'MAT101')['id']}"
    assert admin.patch(url, {"term": 2}, format="json").status_code == 409
    assert admin.delete(url).status_code == 409
    assert act(admin, published, "publish").json()["code"] == "invalid_transition"


def test_revise_copies_the_published_one(admin, college, published):
    second = act(admin, published, "revise")
    assert second.status_code == 201, second.json()
    second = second.json()
    assert (second["revision"], second["status"]) == (2, "draft")
    assert entry(second, "PHY201")["prerequisites"] == ["PHY101"]
    second = add(admin, second, college.PHY101L).json()
    third = act(admin, published, "revise").json()
    assert third["revision"] == 3 and "PHY101L" not in [
        c["course"]["code"] for t in third["terms"] for c in t["courses"]
    ]
    assert act(admin, second, "revise").json()["code"] == "invalid_transition"
    assert admin.get(f"{API}/curricula/{published['id']}").json()["status"] == "published"


def test_retire(admin, college, published):
    made = draft(admin, college, regulation="R2027").json()
    assert act(admin, made, "retire").json()["code"] == "invalid_transition"
    retired = act(admin, published, "retire").json()
    assert retired["status"] == "retired"
    assert add(admin, retired, college.PHY101L).status_code == 409


def test_department_manager_reads_but_cannot_publish_elsewhere(world, admin, college, client_for):
    made = draft(admin, college).json()
    add(admin, made, college.PHY101)
    shown = admin.get(f"{API}/curricula/{made['id']}").json()
    chemist = client_for(world.a.slug, factories.member(world.a, role="registrar", scope=college.chemistry))
    assert chemist.get(f"{API}/curricula/{made['id']}").status_code == 200
    assert act(chemist, shown, "publish").status_code == 403
    physicist = client_for(world.a.slug, factories.member(world.a, role="registrar", scope=college.physics))
    assert act(physicist, shown, "publish").status_code == 200


def test_isolation(world, admin, college, client_for):
    from admissions.tests.conftest import switch_on

    made = draft(admin, college).json()
    switch_on(world.b, modules=("admissions", "students", "academics"))
    birch = client_for(world.b.slug, world.b_admin)
    assert birch.get(f"{API}/curricula/{made['id']}").status_code == 404
    assert birch.get(f"{API}/programs/{college.program.id}/curricula").status_code == 404
    other = Course.objects.create(institution=world.b, code="X1", title="X", credits=1, kind="theory")
    assert fields(add(admin, made, other)) == ["course"]
