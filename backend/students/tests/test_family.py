"""The family portal API: only children with an active, in-effect link, only what the link shares (S4B-08)."""

import datetime as dt

from accounts.models import Membership, User
from accounts.permissions import today_for
from admissions.tests.conftest import APPS, applicant, switch_on
from students import guardians
from students.models import Enrollment, GuardianLink, Person, Student

FAMILY = "/api/v1/family/children"
EVIDENCE = {
    "authority_basis": "parent",
    "verification_method": "documents_in_person",
    "verification_reference": "Aadhaar 1234 seen",
    "restrictions": "No contact with the father.",
}


def verified(world, link, **changes):
    link.refresh_from_db()
    return guardians.verify(world.a_admin, link, link.version, {**EVIDENCE, **changes})


def asha(world, client_for, host=None):
    return client_for(host or world.a.slug, User.objects.get(username="asha.parent"))


def test_proposed_link_shows_nothing(world, enrolled, client_for):
    family = asha(world, client_for)
    assert family.get(FAMILY).status_code == 404  # still an applicant: no family portal yet
    Membership.objects.filter(user__username="asha.parent").update(kind="guardian")
    assert family.get(FAMILY).json() == []
    assert family.get(f"{FAMILY}/{enrolled.id}").status_code == 404


def test_active_link_shows_child_then_revoke_hides(world, enrolled, client_for):
    link = verified(world, enrolled.guardian_links.get())
    family = asha(world, client_for)
    [child] = family.get(FAMILY).json()
    assert (child["id"], child["number"], child["shared"]) == (str(enrolled.id), enrolled.number, True)
    assert child["enrollment"]["place_label"] == "Class 1" and child["status"] == "active"
    assert family.get(f"{FAMILY}/{enrolled.id}").json()["number"] == enrolled.number
    guardians.revoke(world.a_admin, link, link.version, "Moved away")
    assert family.get(FAMILY).json() == []
    assert family.get(f"{FAMILY}/{enrolled.id}").status_code == 404


def test_ended_link_hides_child(world, enrolled, client_for):
    """Review Focus 1."""
    today = today_for(world.a)
    verified(
        world,
        enrolled.guardian_links.get(),
        starts_on=today - dt.timedelta(days=10),
        ends_on=today - dt.timedelta(days=1),
    )
    assert asha(world, client_for).get(FAMILY).json() == []


def test_record_off_is_neutral(world, enrolled, client_for):
    verified(world, enrolled.guardian_links.get(), access={"record": False})
    [child] = asha(world, client_for).get(FAMILY).json()
    assert child == {"id": str(enrolled.id), "full_name": enrolled.person.full_name, "shared": False}


def test_other_family_child_404(world, enrolled, client_for):
    verified(world, enrolled.guardian_links.get())
    ravi = applicant(world.a, "ravi.parent")
    Membership.objects.filter(user=ravi).update(kind="guardian")
    other = client_for(world.a.slug, ravi)
    assert other.get(FAMILY).json() == []
    assert other.get(f"{FAMILY}/{enrolled.id}").status_code == 404


def test_other_institution_student_404(world, enrolled, client_for):
    """Review Focus 2: an active link at another institution is no key at this one."""
    verified(world, enrolled.guardian_links.get())
    user = User.objects.get(username="asha.parent")
    Membership.objects.create(institution=world.b, user=user, kind="guardian")
    person = Person.objects.create(institution=world.b, full_name="Birch Child")
    theirs = Student.objects.create(
        institution=world.b, person=person, number="2027-0001", admitted_on=dt.date(2026, 10, 1)
    )
    Enrollment.objects.create(
        student=theirs,
        institution=world.b,
        academic_year="2027–28",
        place_code="Y1",
        place_label="Year 1",
        entry_date=dt.date(2027, 6, 1),
    )
    adult = Person.objects.create(institution=world.b, full_name="Asha Rao")
    GuardianLink.objects.create(
        institution=world.b, student=theirs, adult=adult, user=user, relationship="Mother", status="active",
        access_record=True, starts_on=dt.date(2026, 1, 1), source="staff",
    )  # fmt: skip
    family = asha(world, client_for)
    assert [child["id"] for child in family.get(FAMILY).json()] == [str(enrolled.id)]
    assert family.get(f"{FAMILY}/{theirs.id}").status_code == 404


def test_payload_has_no_evidence_or_other_guardians(world, enrolled, client_for):
    verified(world, enrolled.guardian_links.get())
    grandmother = guardians.propose(world.a_admin, enrolled, {"full_name": "Lakshmi Rao"}, "Grandmother")
    verified(world, grandmother, login={"username": "lakshmi.rao", "password": "Welcome-2027-pass"})
    family = asha(world, client_for)
    text = str(family.get(FAMILY).json()) + str(family.get(f"{FAMILY}/{enrolled.id}").json())
    for secret in ("No contact", "Aadhaar", "Lakshmi", "documents_in_person", "Grandmother"):
        assert secret not in text


def test_guardian_keeps_applicant_pages(world, enrolled, client_for):
    verified(world, enrolled.guardian_links.get())
    family = asha(world, client_for)
    mine = family.get(APPS)
    assert mine.status_code == 200 and mine.json()["count"] == 1


def test_staff_and_students_cannot_use_family(world, enrolled, client_for):
    for login in (world.a_admin, enrolled.user):
        assert client_for(world.a.slug, login).get(FAMILY).status_code == 404


def test_guardian_cannot_reach_staff_or_student_api(world, enrolled, client_for):
    verified(world, enrolled.guardian_links.get())
    family = asha(world, client_for)
    assert family.get("/api/v1/institution/students").status_code == 403
    assert family.get("/api/v1/institution").status_code == 403
    assert family.get("/api/v1/student/me").status_code == 404


def test_module_off_family_sees_nothing(world, enrolled, client_for):
    verified(world, enrolled.guardian_links.get())
    switch_on(world.a, modules=("admissions",))
    family = asha(world, client_for)
    assert family.get(FAMILY).json() == []
    assert family.get(f"{FAMILY}/{enrolled.id}").status_code == 404
