"""Verifying and revoking guardian links (slice 4b S4B-03 to S4B-07)."""

import datetime as dt

from accounts.models import Membership, User
from accounts.permissions import today_for
from admissions.tests.conftest import switch_on
from admissions.tests.test_enrollment import FIRST
from common.models import AuditEvent
from students.models import GuardianLink
from testing import factories


def url(student, tail=""):
    return f"/api/v1/institution/students/{student.id}/guardians{tail}"


def verify(client, student, link, **changes):
    body = {
        "version": link.version,
        "authority_basis": "parent",
        "verification_method": "documents_in_person",
        "verification_reference": "Aadhaar seen at the office",
        "access": {"record": True},
        **changes,
    }
    return client.post(url(student, f"/{link.id}/verify"), body, format="json")


def staff_link(client, student, name="Lakshmi Rao"):
    body = {"adult": {"full_name": name, "phone": "+91 90000 55555"}, "relationship": "Grandmother"}
    created = client.post(url(student), body, format="json")
    assert created.status_code == 201, created.json()
    return GuardianLink.objects.get(pk=created.json()["id"])


def test_verify_activates_and_makes_a_guardian(world, enrolled, registrar):
    link = enrolled.guardian_links.get()
    done = verify(registrar, enrolled, link)
    assert done.status_code == 200, done.json()
    link.refresh_from_db()
    assert (link.status, link.access_record, link.access_fees, link.access_messages) == ("active", True, False, False)
    assert link.starts_on == today_for(world.a) and link.verified_by is not None
    assert Membership.objects.get(user=link.user, institution=world.a).kind == "guardian"
    assert AuditEvent.objects.filter(action="student.guardian_verified", object_id=str(enrolled.id)).exists()


def test_verify_twice_and_stale_version_409(world, enrolled, registrar):
    link = enrolled.guardian_links.get()
    stale = verify(registrar, enrolled, link, version=link.version + 5)
    assert stale.status_code == 409 and stale.json()["code"] == "version_conflict"
    assert verify(registrar, enrolled, link).status_code == 200
    link.refresh_from_db()
    again = verify(registrar, enrolled, link)
    assert again.status_code == 409 and again.json()["code"] == "invalid_transition"


def test_adult_student_needs_consent(world, enrolled, registrar):
    today = today_for(world.a)
    person = enrolled.person
    person.date_of_birth = today.replace(year=today.year - 18)
    person.save()
    link = enrolled.guardian_links.get()
    refused = verify(registrar, enrolled, link)
    assert refused.status_code == 422
    assert [error["field"] for error in refused.json()["errors"]] == ["authority_basis"]
    assert verify(registrar, enrolled, link, authority_basis="student_consent").status_code == 200


def test_new_login_for_guardian(world, enrolled, registrar):
    first = staff_link(registrar, enrolled)
    made = verify(registrar, enrolled, first, login={"username": "lakshmi.rao", "password": FIRST})
    assert made.status_code == 200, made.json()
    login = User.objects.get(username="lakshmi.rao")
    assert login.must_change_password and login.check_password(FIRST)
    assert Membership.objects.get(user=login).kind == "guardian"
    second = staff_link(registrar, enrolled, name="Ravi Rao")
    users = User.objects.count()
    taken = verify(registrar, enrolled, second, login={"username": "Lakshmi.Rao", "password": FIRST})
    assert taken.status_code == 422
    assert [error["field"] for error in taken.json()["errors"]] == ["login.username"]
    second.refresh_from_db()
    assert second.status == "proposed" and User.objects.count() == users


def test_staff_or_student_login_cannot_be_linked(world, enrolled, registrar):
    for login in (world.a_admin, enrolled.user):
        link = staff_link(registrar, enrolled, name=f"Adult of {login.username}")
        GuardianLink.objects.filter(pk=link.pk).update(user=login)
        link.refresh_from_db()
        refused = verify(registrar, enrolled, link)
        assert refused.status_code == 409 and refused.json()["code"] == "kind_conflict"
        link.refresh_from_db()
        assert link.status == "proposed"


def test_revoke_needs_reason_and_is_final(world, enrolled, registrar):
    link = enrolled.guardian_links.get()
    verify(registrar, enrolled, link)
    link.refresh_from_db()
    revoke = url(enrolled, f"/{link.id}/revoke")
    assert registrar.post(revoke, {"version": link.version, "reason": " "}, format="json").status_code == 422
    done = registrar.post(revoke, {"version": link.version, "reason": "Court order received."}, format="json")
    assert done.status_code == 200 and done.json()["status"] == "revoked"
    link.refresh_from_db()
    assert registrar.post(revoke, {"version": link.version, "reason": "Again"}, format="json").status_code == 409
    assert verify(registrar, enrolled, link).status_code == 409


def test_read_without_manage_hides_evidence(world, enrolled, registrar, client_for):
    link = enrolled.guardian_links.get()
    verify(registrar, enrolled, link, restrictions="No contact with the father.")
    principal = client_for(world.a.slug, factories.member(world.a, role="principal"))
    rows = principal.get(url(enrolled)).json()
    assert [row["status"] for row in rows] == ["active"]
    assert not {"restrictions", "verification_reference", "authority_basis"} & set(rows[0])
    assert "No contact" not in str(rows)
    assert "restrictions" in registrar.get(url(enrolled)).json()[0]
    record = f"/api/v1/institution/students/{enrolled.id}"
    assert principal.get(record).json()["can_manage_guardians"] is False
    assert registrar.get(record).json()["can_manage_guardians"] is True
    link.refresh_from_db()
    assert (
        principal.post(url(enrolled, f"/{link.id}/revoke"), {"version": link.version, "reason": "x"}).status_code == 403
    )
    assert (
        principal.post(url(enrolled), {"adult": {"full_name": "X"}, "relationship": "Uncle"}, format="json").status_code
        == 403
    )


def test_other_campus_reader_gets_404(world, enrolled, client_for):
    city = factories.campus(world.a, code="CITY", name="City campus")
    reader = client_for(world.a.slug, factories.member(world.a, role="principal", scope=city))
    assert reader.get(url(enrolled)).status_code == 404


def test_other_institution_ids_404(world, enrolled, registrar, client_for):
    birch = client_for(world.b.slug, world.b_admin)
    assert birch.get(url(enrolled)).status_code == 404
    link = enrolled.guardian_links.get()
    assert birch.post(url(enrolled, f"/{link.id}/verify"), {"version": link.version}, format="json").status_code == 404
    fake = registrar.post(url(enrolled, f"/{world.a.id}/verify"), {"version": 1}, format="json")
    assert fake.status_code == 404


def test_guardians_need_students_module(world, enrolled, registrar):
    switch_on(world.a, modules=("admissions",))
    assert registrar.get(url(enrolled)).status_code == 404


def test_needs_adult_review_flag(world, enrolled, registrar):
    link = enrolled.guardian_links.get()
    verify(registrar, enrolled, link)
    assert registrar.get(url(enrolled)).json()[0]["needs_adult_review"] is False
    today = today_for(world.a)
    GuardianLink.objects.filter(pk=link.pk).update(verified_at=dt.datetime(today.year - 1, 1, 1, tzinfo=dt.UTC))
    person = enrolled.person
    person.date_of_birth = today.replace(year=today.year - 18) - dt.timedelta(days=30)
    person.save()
    assert registrar.get(url(enrolled)).json()[0]["needs_adult_review"] is True
