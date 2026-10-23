"""Moving a section on to next year (slice 5a S5A-06, TST-035)."""

import datetime as dt

from academics.models import EnrollmentPeriod, Section
from accounts.permissions import today_for
from students import withdrawal
from students.models import Enrollment, Student
from testing import factories

from .conftest import API, enrolled_student
from .test_placement import make_section, place


def next_section(school, code="7A", capacity=40, grade=None):
    return Section.objects.create(
        institution=school.year.institution, year=school.next_year, grade=grade or school.c7, campus=school.main,
        code=code, capacity=capacity,
    )  # fmt: skip


def preview(client, source, target, mode="promote"):
    return client.post(
        f"{API}/sections/{source.id}/move-up/preview", {"target": str(target.id), "mode": mode}, format="json"
    )


def commit(client, source, target, students, mode="promote"):
    body = {"target": str(target.id), "mode": mode, "students": [str(s.id) for s in students]}
    return client.post(f"{API}/sections/{source.id}/move-up", body, format="json")


def test_tst035_one_new_placement_per_student_and_nothing_else(world, admin, school):
    source, target = make_section(school), next_section(school)
    kids = [enrolled_student(world.a, f"2026-000{n}", name=f"Kid {n}") for n in range(1, 4)]
    place(admin, source, *kids)
    counts = (Student.objects.count(), Enrollment.objects.count())
    rows = preview(admin, source, target).json()
    assert [row["action"] for row in rows] == ["move", "move", "move"]
    done = commit(admin, source, target, kids)
    assert done.status_code == 200, done.json()
    assert done.json()["moved"] == 3
    assert EnrollmentPeriod.objects.filter(year=school.next_year, section=target).count() == 3
    assert (
        EnrollmentPeriod.objects.filter(year=school.year, section=source, state="active").count() == 3
    )  # history kept
    assert (Student.objects.count(), Enrollment.objects.count()) == counts
    again = commit(admin, source, target, kids)
    assert again.json()["moved"] == 0
    assert EnrollmentPeriod.objects.filter(year=school.next_year).count() == 3


def test_withdrawn_and_already_placed_are_skipped(world, admin, school):
    """Review Focus 3."""
    source, target, elsewhere = make_section(school), next_section(school), next_section(school, code="7B")
    stays, leaves, placed_early = (enrolled_student(world.a, f"2026-000{n}", name=f"Kid {n}") for n in range(1, 4))
    place(admin, source, stays, leaves, placed_early)
    Enrollment.objects.filter(student=leaves).update(entry_date=dt.date(2026, 6, 1))
    leaves.refresh_from_db()
    withdrawal.withdraw(world.a_admin, leaves, leaves.version, today_for(world.a), "Moved away")
    place(admin, elsewhere, placed_early)
    actions = {row["student"]["number"]: row["action"] for row in preview(admin, source, target).json()}
    assert actions == {"2026-0001": "move", "2026-0002": "withdrawn", "2026-0003": "already_placed"}
    done = commit(admin, source, target, [stays, leaves, placed_early]).json()
    assert done["moved"] == 1
    assert (
        EnrollmentPeriod.objects.filter(enrollment__student=placed_early, year=school.next_year).get().section
        == elsewhere
    )


def test_repeat_keeps_the_grade_and_marks_it(world, admin, school):
    source = make_section(school)
    same_grade = next_section(school, code="6A", grade=school.c6)
    kid = enrolled_student(world.a, "2026-0001")
    place(admin, source, kid)
    assert preview(admin, source, same_grade, mode="promote").status_code == 422
    assert commit(admin, source, same_grade, [kid], mode="repeat").json()["moved"] == 1
    assert EnrollmentPeriod.objects.get(year=school.next_year).is_repeat is True


def test_over_capacity_moves_nobody(world, admin, school):
    source, small = make_section(school), next_section(school, capacity=1)
    kids = [enrolled_student(world.a, f"2026-000{n}") for n in (1, 2)]
    place(admin, source, *kids)
    refused = commit(admin, source, small, kids)
    assert refused.status_code == 409 and refused.json()["code"] == "section_full"
    assert not EnrollmentPeriod.objects.filter(year=school.next_year).exists()


def test_target_must_be_a_later_year(world, admin, school):
    source, same_year = make_section(school), make_section(school, code="6B")
    refused = preview(admin, source, same_year)
    assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "target"


def test_both_sections_must_be_in_scope(world, on, admin, school, client_for):
    city_manager = client_for(world.a.slug, factories.member(world.a, role="registrar", scope=school.city))
    source, target = make_section(school), next_section(school)
    assert preview(city_manager, source, target).status_code in (403, 404)
