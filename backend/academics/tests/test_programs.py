"""Programs and courses (slice 5b S5B-01, S5B-03, S5B-08)."""

import pytest

from admissions.tests.conftest import switch_on
from testing import factories

from .conftest import API


@pytest.fixture
def depts(world, on):
    return factories.department(world.a, code="PHY", name="Physics"), factories.department(
        world.a, code="CHE", name="Chemistry"
    )


def program_body(**changes):
    return {"code": "BSC-PHY", "name": "B.Sc Physics", "qualification": "B.Sc", "length_terms": 6, **changes}


def course_body(**changes):
    return {"code": "PHY101", "title": "Mechanics", "credits": "4", "kind": "theory", **changes}


def fields(response):
    return [e["field"] for e in response.json()["errors"]]


def test_programs_create_and_rules(world, admin, depts, client_for):
    physics, _ = depts
    made = admin.post(f"{API}/programs", program_body(department=str(physics.id)), format="json")
    assert made.status_code == 201, made.json()
    assert made.json()["department"]["name"] == "Physics"
    again = admin.post(f"{API}/programs", program_body(), format="json")
    assert again.status_code == 422 and fields(again) == ["code"]
    assert fields(admin.post(f"{API}/programs", program_body(code="X", length_terms=17), format="json")) == [
        "length_terms"
    ]
    birch_dept = factories.department(world.b, code="B", name="Birch")
    elsewhere = admin.post(f"{API}/programs", program_body(code="Y", department=str(birch_dept.id)), format="json")
    assert fields(elsewhere) == ["department"]
    renamed = admin.patch(
        f"{API}/programs/{made.json()['id']}",
        {"version": made.json()["version"], "name": "B.Sc (Hons) Physics"},
        format="json",
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "B.Sc (Hons) Physics"


def test_course_credits_in_halves(world, admin, depts):
    assert admin.post(f"{API}/courses", course_body(), format="json").status_code == 201
    assert admin.post(f"{API}/courses", course_body(code="PHY101L", credits="1.5"), format="json").status_code == 201
    assert fields(admin.post(f"{API}/courses", course_body(code="A", credits="1.3"), format="json")) == ["credits"]
    assert fields(admin.post(f"{API}/courses", course_body(code="B", credits="31"), format="json")) == ["credits"]
    assert fields(admin.post(f"{API}/courses", course_body(), format="json")) == ["code"]


def test_department_scope(world, admin, depts, client_for):
    physics, chemistry = depts
    manager = client_for(world.a.slug, factories.member(world.a, role="registrar", scope=physics))
    mine = manager.post(f"{API}/courses", course_body(department=str(physics.id)), format="json")
    assert mine.status_code == 201, mine.json()
    assert (
        manager.post(
            f"{API}/courses", course_body(code="CHE101", department=str(chemistry.id)), format="json"
        ).status_code
        == 403
    )
    assert manager.post(f"{API}/courses", course_body(code="GEN101"), format="json").status_code == 403
    theirs = admin.post(
        f"{API}/courses", course_body(code="CHE102", department=str(chemistry.id)), format="json"
    ).json()
    patched = manager.patch(
        f"{API}/courses/{theirs['id']}", {"version": theirs["version"], "title": "Mine now"}, format="json"
    )
    assert patched.status_code == 403
    moved = manager.patch(
        f"{API}/courses/{mine.json()['id']}",
        {"version": mine.json()["version"], "department": str(chemistry.id)},
        format="json",
    )
    assert moved.status_code == 403


def test_courses_search_and_page(world, admin, depts, client_for):
    for n in range(7):
        admin.post(f"{API}/courses", course_body(code=f"PHY{n}", title=f"Physics {n}"), format="json")
    admin.post(f"{API}/courses", course_body(code="MAT101", title="Calculus"), format="json")
    listed = admin.get(f"{API}/courses").json()
    assert listed["count"] == 8 and len(listed["results"]) == 5
    assert admin.get(f"{API}/courses", {"search": "calc"}).json()["count"] == 1
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.get(f"{API}/courses").status_code == 200
    assert teacher.post(f"{API}/courses", course_body(code="T1"), format="json").status_code == 403


def test_isolation_and_module(world, admin, depts, client_for):
    made = admin.post(f"{API}/programs", program_body(), format="json").json()
    switch_on(world.b, modules=("admissions", "students", "academics"))
    birch = client_for(world.b.slug, world.b_admin)
    assert birch.get(f"{API}/programs/{made['id']}").status_code == 404
    switch_on(world.a, modules=("admissions", "students"))
    assert admin.get(f"{API}/programs").status_code == 404


def test_a_published_regulation_keeps_its_credits_and_terms(admin, depts):
    """Final review: a published regulation must not change through its courses or program."""
    course = admin.post(f"{API}/courses", course_body(), format="json").json()
    program = admin.post(f"{API}/programs", program_body(), format="json").json()
    draft = admin.post(
        f"{API}/programs/{program['id']}/curricula",
        {"regulation": "R1", "cohort": 2026, "credits_required": "120"},
        format="json",
    ).json()
    shown = admin.post(
        f"{API}/curricula/{draft['id']}/courses", {"course": course["id"], "category": "core", "term": 4}, format="json"
    ).json()
    url = f"{API}/courses/{course['id']}"
    in_draft = admin.patch(url, {"version": course["version"], "credits": "3"}, format="json")
    assert in_draft.status_code == 200, in_draft.json()
    course = in_draft.json()
    admin.post(f"{API}/curricula/{draft['id']}/publish", {"version": shown["version"]}, format="json")
    frozen = admin.patch(url, {"version": course["version"], "credits": "2"}, format="json")
    assert frozen.status_code == 409 and frozen.json()["code"] == "in_use"
    assert (
        admin.patch(url, {"version": course["version"], "title": "Classical mechanics"}, format="json").status_code
        == 200
    )
    program_url = f"{API}/programs/{program['id']}"
    shorter = admin.patch(program_url, {"version": program["version"], "length_terms": 3}, format="json")
    assert shorter.status_code == 422 and [e["field"] for e in shorter.json()["errors"]] == ["length_terms"]
    assert (
        admin.patch(program_url, {"version": program["version"], "length_terms": 4}, format="json").status_code == 200
    )


def test_department_scope_for_programs_and_own_edits(world, depts, client_for):
    physics, chemistry = depts
    manager = client_for(world.a.slug, factories.member(world.a, role="registrar", scope=physics))
    mine = manager.post(f"{API}/courses", course_body(department=str(physics.id)), format="json").json()
    own = manager.patch(
        f"{API}/courses/{mine['id']}", {"version": mine["version"], "title": "Mechanics I"}, format="json"
    )
    assert own.status_code == 200
    assert manager.post(f"{API}/programs", program_body(department=str(physics.id)), format="json").status_code == 201
    assert (
        manager.post(f"{API}/programs", program_body(code="C", department=str(chemistry.id)), format="json").status_code
        == 403
    )
    assert manager.post(f"{API}/programs", program_body(code="W"), format="json").status_code == 403


def test_another_institutions_course_is_not_found(world, admin, depts, client_for):
    made = admin.post(f"{API}/courses", course_body(), format="json").json()
    switch_on(world.b, modules=("admissions", "students", "academics"))
    birch = client_for(world.b.slug, world.b_admin)
    assert (
        birch.patch(
            f"{API}/courses/{made['id']}", {"version": made["version"], "title": "X"}, format="json"
        ).status_code
        == 404
    )
