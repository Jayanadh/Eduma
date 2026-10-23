"""Sections and teaching assignments (slice 5a S5A-03, S5A-05, S5A-07)."""

from academics.models import EnrollmentPeriod, TeachingAssignment
from accounts.models import Membership
from admissions.tests.conftest import applicant, switch_on
from testing import factories

from .conftest import API, enrolled_student, section_body


def fields(response):
    return [e["field"] for e in response.json()["errors"]]


def test_create_and_rules(world, admin, school):
    made = admin.post(f"{API}/sections", section_body(school), format="json")
    assert made.status_code == 201, made.json()
    assert made.json()["grade"]["name"] == "Class 6" and made.json()["placed"] == 0
    again = admin.post(f"{API}/sections", section_body(school), format="json")
    assert again.status_code == 422 and fields(again) == ["code"]
    parent = applicant(world.a, "asha.parent")
    not_staff = admin.post(
        f"{API}/sections",
        section_body(school, code="6B", class_teacher=str(Membership.objects.get(user=parent).id)),
        format="json",
    )
    assert not_staff.status_code == 422 and fields(not_staff) == ["class_teacher"]
    birch_campus = factories.campus(world.b, code="B", name="Birch")
    elsewhere = admin.post(
        f"{API}/sections", section_body(school, code="6C", campus=str(birch_campus.id)), format="json"
    )
    assert elsewhere.status_code == 422 and fields(elsewhere) == ["campus"]


def test_capacity_not_below_placed(world, admin, school):
    section = admin.post(f"{API}/sections", section_body(school, capacity=2), format="json").json()
    from academics.models import Section

    row = Section.objects.get(pk=section["id"])
    for number in ("2026-0001", "2026-0002"):
        student = enrolled_student(world.a, number)
        EnrollmentPeriod.objects.create(
            enrollment=student.enrollments.get(),
            institution=world.a,
            year=school.year,
            section=row,
            grade=school.c6,
            campus=school.main,
        )
    shrink = admin.patch(
        f"{API}/sections/{section['id']}", {"version": section["version"], "capacity": 1}, format="json"
    )
    assert shrink.status_code == 422 and fields(shrink) == ["capacity"]


def test_closed_year_is_read_only(world, admin, school):
    school.year.status = "closed"
    school.year.save()
    refused = admin.post(f"{API}/sections", section_body(school), format="json")
    assert refused.status_code == 409


def test_campus_scope(world, on, school, client_for):
    city_manager = client_for(world.a.slug, factories.member(world.a, role="registrar", scope=school.city))
    assert (
        city_manager.post(
            f"{API}/sections", section_body(school, campus=str(school.city.id)), format="json"
        ).status_code
        == 201
    )
    assert city_manager.post(f"{API}/sections", section_body(school, code="6M"), format="json").status_code == 403


def test_list_filters(world, admin, school):
    admin.post(f"{API}/sections", section_body(school), format="json")
    admin.post(f"{API}/sections", section_body(school, code="7A", grade=str(school.c7.id)), format="json")
    admin.post(
        f"{API}/sections",
        section_body(school, code="7B", grade=str(school.c7.id), year=str(school.next_year.id)),
        format="json",
    )
    assert admin.get(f"{API}/sections", {"year": str(school.year.id)}).json()["count"] == 2
    assert [
        s["code"] for s in admin.get(f"{API}/sections", {"grade": str(school.c7.id), "page_size": 20}).json()["results"]
    ] == ["7B", "7A"]  # newest year first


def test_teachers_added_and_ended(world, admin, school):
    section = admin.post(f"{API}/sections", section_body(school), format="json").json()
    teacher = Membership.objects.get(user=factories.member(world.a, role="teacher"))
    added = admin.post(
        f"{API}/sections/{section['id']}/teachers",
        {"membership": str(teacher.id), "subject": str(school.science.id)},
        format="json",
    )
    assert added.status_code == 201, added.json()
    detail = admin.get(f"{API}/sections/{section['id']}").json()
    assert [(t["subject"]["name"], t["in_effect"]) for t in detail["teachers"]] == [("Science", True)]
    assignment = TeachingAssignment.objects.get()
    ended = admin.post(f"{API}/sections/{section['id']}/teachers/{assignment.id}/end", {}, format="json")
    assert ended.status_code == 200
    assert [t["in_effect"] for t in admin.get(f"{API}/sections/{section['id']}").json()["teachers"]] == [False]


def test_other_institution_ids(world, admin, school, client_for):
    section = admin.post(f"{API}/sections", section_body(school), format="json").json()
    switch_on(world.b, modules=("admissions", "students", "academics"))
    birch = client_for(world.b.slug, world.b_admin)
    assert birch.get(f"{API}/sections/{section['id']}").status_code == 404
    assert birch.get(f"{API}/sections").json()["count"] == 0


def test_staff_to_choose_from(world, admin, school, client_for):
    factories.member(world.a, role="teacher", full_name="Tara Teacher")
    applicant(world.a, "asha.parent")
    names = [row["full_name"] for row in admin.get(f"{API}/staff").json()]
    assert "Tara Teacher" in names and "Asha Parent" not in names
    assert set(admin.get(f"{API}/staff").json()[0]) == {"id", "full_name"}
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.get(f"{API}/staff").status_code == 403
