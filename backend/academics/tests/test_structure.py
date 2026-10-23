"""Years, terms, grades and subjects (slice 5a S5A-01, S5A-02)."""

from academics.models import AcademicYear
from admissions.tests.conftest import switch_on
from testing import factories

from .conftest import API, make_year


def errors(response):
    return [e["field"] for e in response.json()["errors"]]


def test_years_must_not_overlap(world, admin):
    assert make_year(admin).status_code == 201
    overlapping = make_year(admin, code="2027–28", start="2027-03-01", end="2028-02-28")
    assert overlapping.status_code == 422 and errors(overlapping) == ["starts_on"]
    backwards = make_year(admin, code="2028–29", start="2029-03-01", end="2028-06-01")
    assert backwards.status_code == 422 and errors(backwards) == ["ends_on"]
    assert make_year(admin, code="2026–27", start="2030-06-01", end="2031-03-31").status_code == 422  # code taken


def test_terms_inside_the_year_and_apart(world, admin):
    year = make_year(admin).json()
    terms = f"{API}/years/{year['id']}/terms"
    ok = admin.post(
        terms, {"name": "Term 1", "ordinal": 1, "starts_on": "2026-06-01", "ends_on": "2026-10-31"}, format="json"
    )
    assert ok.status_code == 201, ok.json()
    outside = admin.post(
        terms, {"name": "Term 3", "ordinal": 3, "starts_on": "2027-01-01", "ends_on": "2027-04-30"}, format="json"
    )
    assert outside.status_code == 422 and errors(outside) == ["ends_on"]
    overlap = admin.post(
        terms, {"name": "Term 2", "ordinal": 2, "starts_on": "2026-10-01", "ends_on": "2027-03-31"}, format="json"
    )
    assert overlap.status_code == 422 and errors(overlap) == ["starts_on"]
    listed = admin.get(f"{API}/years").json()
    assert [t["name"] for t in listed[0]["terms"]] == ["Term 1"]


def test_shrinking_a_year_past_a_term_is_refused(world, admin):
    """Review Focus 5."""
    year = make_year(admin).json()
    admin.post(
        f"{API}/years/{year['id']}/terms",
        {"name": "Term 2", "ordinal": 2, "starts_on": "2026-11-01", "ends_on": "2027-03-31"},
        format="json",
    )
    current = admin.get(f"{API}/years/{year['id']}").json()
    refused = admin.patch(
        f"{API}/years/{year['id']}", {"version": current["version"], "ends_on": "2027-02-28"}, format="json"
    )
    assert refused.status_code == 422 and errors(refused) == ["ends_on"]
    assert str(AcademicYear.objects.get().ends_on) == "2027-03-31"


def test_one_current_year(world, admin):
    make_year(admin, status="current")
    second = make_year(admin, code="2027–28", start="2027-06-01", end="2028-03-31", status="current")
    assert second.status_code == 409 and second.json()["code"] == "another_current_year"


def test_delete_only_a_planned_empty_year(world, admin):
    year = make_year(admin).json()
    assert admin.delete(f"{API}/years/{year['id']}").status_code == 204
    current = make_year(admin, status="current").json()
    assert admin.delete(f"{API}/years/{current['id']}").status_code == 409


def test_grades_and_subjects(world, admin):
    grade = admin.post(f"{API}/grades", {"code": "C6", "name": "Class 6", "order": 6}, format="json")
    assert grade.status_code == 201
    assert admin.post(f"{API}/grades", {"code": "C6", "name": "Again", "order": 7}, format="json").status_code == 422
    renamed = admin.patch(
        f"{API}/grades/{grade.json()['id']}", {"version": grade.json()["version"], "name": "Grade 6"}, format="json"
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "Grade 6"
    subject = admin.post(f"{API}/subjects", {"code": "SCI", "name": "Science"}, format="json")
    assert subject.status_code == 201
    assert [s["name"] for s in admin.get(f"{API}/subjects").json()] == ["Science"]


def test_who_may_change_and_read(world, admin, client_for):
    city = factories.campus(world.a, code="CITY", name="City campus")
    city_manager = client_for(world.a.slug, factories.member(world.a, role="registrar", scope=city))
    assert make_year(city_manager).status_code == 403
    assert (
        city_manager.post(f"{API}/grades", {"code": "C1", "name": "Class 1", "order": 1}, format="json").status_code
        == 403
    )
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    make_year(admin)
    assert teacher.get(f"{API}/years").status_code == 200
    assert make_year(teacher, code="2027–28", start="2027-06-01", end="2028-03-31").status_code == 403


def test_module_off(world, admin):
    switch_on(world.a, modules=("admissions", "students"))
    assert admin.get(f"{API}/years").status_code == 404
