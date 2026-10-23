"""Slice 5a final review findings, each pinned by a test that failed first."""

from academics.models import EnrollmentPeriod, Section
from accounts.models import Membership
from accounts.permissions import today_for
from students import withdrawal
from testing import factories

from .conftest import API, enrolled_student, section_body
from .test_moveup import commit, next_section, preview
from .test_placement import make_section, place


def take_out(client, section, student):
    return client.delete(f"{API}/sections/{section.id}/students/{student.id}")


def test_a_taken_out_student_can_be_placed_again(world, admin, school):
    """Critical: Take out must not leave the student unplaceable for the year."""
    six_a, six_b = make_section(school), make_section(school, code="6B")
    student = enrolled_student(world.a, "2026-0001")
    place(admin, six_a, student)
    assert take_out(admin, six_a, student).status_code == 204
    again = place(admin, six_b, student)
    assert again.status_code == 201, again.json()
    period = EnrollmentPeriod.objects.get()
    assert (period.section, period.state) == (six_b, "active")


def test_taken_out_students_do_not_move_up(world, admin, school):
    source, target = make_section(school), next_section(school)
    stays, out = enrolled_student(world.a, "2026-0001"), enrolled_student(world.a, "2026-0002")
    place(admin, source, stays, out)
    take_out(admin, source, out)
    rows = preview(admin, source, target).json()
    assert [row["student"]["number"] for row in rows] == ["2026-0001"]


def test_reinstating_reopens_only_what_the_withdrawal_ended(world, admin, school):
    section = make_section(school)
    student = enrolled_student(world.a, "2026-0001")
    place(admin, section, student)
    take_out(admin, section, student)
    student.refresh_from_db()
    withdrawal.withdraw(world.a_admin, student, student.version, today_for(world.a), "Moved away")
    student.refresh_from_db()
    withdrawal.reinstate(world.a_admin, student, student.version)
    assert EnrollmentPeriod.objects.get().state == "ended"


def test_withdrawal_leaves_closed_years_alone(world, admin, school):
    source, target = make_section(school), next_section(school)
    student = enrolled_student(world.a, "2026-0001")
    place(admin, source, student)
    commit(admin, source, target, [student])
    school.year.status = "closed"
    school.year.save()
    student.refresh_from_db()
    withdrawal.withdraw(world.a_admin, student, student.version, today_for(world.a), "Moved away")
    states = dict(EnrollmentPeriod.objects.values_list("year__code", "state"))
    assert states == {"2026–27": "active", "2027–28": "ended"}


def test_moving_up_from_a_closed_year(world, admin, school):
    source, target = make_section(school), next_section(school)
    student = enrolled_student(world.a, "2026-0001")
    place(admin, source, student)
    school.year.status = "closed"
    school.year.save()
    assert preview(admin, source, target).status_code == 200
    done = commit(admin, source, target, [student])
    assert done.status_code == 200 and done.json()["moved"] == 1


def test_year_status_only_moves_forward(world, admin, school):
    year = school.next_year

    def to(status):
        year.refresh_from_db()
        return admin.patch(f"{API}/years/{year.id}", {"version": year.version, "status": status}, format="json")

    school.year.status = "closed"
    school.year.save()
    assert to("current").status_code == 200
    refused = to("planned")
    assert refused.status_code == 409 and refused.json()["code"] == "invalid_transition"
    assert to("closed").status_code == 200
    assert to("current").status_code == 409


def test_the_class_teacher_is_one_assignment(world, admin, school, client_for):
    teacher = factories.member(world.a, role="teacher")
    membership = Membership.objects.get(user=teacher)
    made = admin.post(f"{API}/sections", section_body(school, class_teacher=str(membership.id)), format="json").json()
    me = client_for(world.a.slug, teacher)
    classes = me.get("/api/v1/teaching/classes").json()
    assert [(c["section"]["code"], c["class_teacher"]) for c in classes] == [("6A", True)]
    assert me.get(f"/api/v1/teaching/classes/{made['id']}/students").status_code == 200
    other = Membership.objects.get(user=factories.member(world.a, role="teacher", full_name="Second Teacher"))
    six_b = admin.post(f"{API}/sections", section_body(school, code="6B"), format="json").json()
    admin.post(f"{API}/sections/{six_b['id']}/teachers", {"membership": str(other.id), "subject": None}, format="json")
    assert admin.get(f"{API}/sections/{six_b['id']}").json()["class_teacher"]["full_name"] == "Second Teacher"


def test_a_section_with_students_keeps_its_year_grade_and_campus(world, admin, school):
    section = make_section(school)
    place(admin, section, enrolled_student(world.a, "2026-0001"))
    section.refresh_from_db()
    for change in ({"year": str(school.next_year.id)}, {"grade": str(school.c7.id)}, {"campus": str(school.city.id)}):
        refused = admin.patch(f"{API}/sections/{section.id}", {"version": section.version, **change}, format="json")
        assert refused.status_code == 422, change
    assert (
        admin.patch(
            f"{API}/sections/{section.id}", {"version": section.version, "capacity": 30}, format="json"
        ).status_code
        == 200
    )
    closed = make_section(school, code="6Z")
    school.year.status = "closed"
    school.year.save()
    moved = admin.patch(
        f"{API}/sections/{closed.id}", {"version": closed.version, "year": str(school.next_year.id)}, format="json"
    )
    assert moved.status_code == 409
    assert Section.objects.get(pk=closed.pk).year == school.year
