"""Library, transport and hostel (slice 10a; TST-027, TST-028)."""

import datetime as dt
import threading

import pytest
from django.db import connection

from academics.tests.conftest import enrolled_student
from accounts.models import Membership
from accounts.permissions import today_for
from admissions.tests.conftest import switch_on
from campus import library
from campus.models import Copy, Loan
from fees.models import Invoice
from students.models import GuardianLink, Person
from testing import factories

C = "/api/v1/institution/campus"
MODULES = ("students", "fees", "library", "transport", "hostel")


def plan(institution):
    institution.modules = sorted({*institution.modules, *MODULES})
    institution.save()
    switch_on(institution, modules=MODULES)


@pytest.fixture
def k(world, client_for):
    plan(world.a)
    ns = type("K", (), {})()
    ns.today = today_for(world.a)
    ns.asha, ns.ravi, ns.meera = (
        enrolled_student(world.a, f"2026-000{n}", name=name)
        for n, name in ((1, "Asha Rao"), (2, "Ravi Kumar"), (3, "Meera Iyer"))
    )
    ns.librarian = client_for(world.a.slug, factories.member(world.a, role="librarian", username="lib"))
    ns.transport = client_for(world.a.slug, factories.member(world.a, role="transport_officer", username="bus.office"))
    ns.warden = client_for(world.a.slug, factories.member(world.a, role="warden", username="warden"))
    return ns


def title(k, copies=1, **extra):
    body = {
        "title": "Wings of Fire",
        "author": "A. P. J. Abdul Kalam",
        "replacement_cost": "350.00",
        "copies": [f"WF-{n}" for n in range(1, copies + 1)],
        **extra,
    }
    return k.librarian.post(f"{C}/titles", body, format="json").json()


def issue(k, student, accession):
    return k.librarian.post(f"{C}/loans", {"accession": accession, "student": str(student.id)}, format="json")


@pytest.mark.django_db(transaction=True)
def test_two_borrowers_race_for_the_last_copy(world):
    """TST-027."""
    plan(world.a)
    a, b = enrolled_student(world.a, "2026-0001"), enrolled_student(world.a, "2026-0002")
    staff = factories.member(world.a, role="librarian", username="lib")
    made = library.add_title(staff, world.a, {"title": "Wings of Fire", "copies": ["WF-1"]})
    results = []

    def go(student):
        try:
            library.issue(staff, world.a, "WF-1", student=student)
            results.append("ok")
        except Exception as error:  # noqa: BLE001 — the losing thread's error is the point
            results.append(getattr(error, "problem_code", repr(error)))
        finally:
            connection.close()

    threads = [threading.Thread(target=go, args=(s,)) for s in (a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["copy_unavailable", "ok"]
    assert Loan.objects.filter(copy__title_id=made.id, status="active").count() == 1


def test_returns_fines_waivers_and_lost(world, k):
    title(k, copies=2)
    loan = issue(k, k.asha, "WF-1").json()
    Loan.objects.filter(pk=loan["id"]).update(due_on=k.today - dt.timedelta(days=5))
    back = k.librarian.post(f"{C}/loans/{loan['id']}/return", {}, format="json").json()
    assert back["status"] == "returned" and back["fines"][0]["amount"] == "10.00"
    again = k.librarian.post(f"{C}/loans/{loan['id']}/return", {}, format="json").json()
    assert len(again["fines"]) == 1  # returning twice changes nothing
    invoice = Invoice.objects.get(account__student=k.asha)
    assert invoice.lines.get().amount == 10
    waived = k.librarian.post(
        f"{C}/fines/{back['fines'][0]['id']}/waive", {"reason": "First time"}, format="json"
    ).json()
    assert waived["fines"][0]["waived_reason"] == "First time" and waived["fines"][0]["amount"] == "10.00"
    lost = issue(k, k.ravi, "WF-2").json()
    gone = k.librarian.post(f"{C}/loans/{lost['id']}/lost", {}, format="json").json()
    assert gone["status"] == "lost" and gone["fines"][0]["amount"] == "350.00"
    assert Copy.objects.get(accession="WF-2").status == "lost"


def test_limits_overdue_and_reservations(world, k):
    title(k, copies=5)
    for n in range(1, 4):
        assert issue(k, k.asha, f"WF-{n}").status_code == 201
    assert issue(k, k.asha, "WF-4").status_code == 422  # three at a time for students
    overdue = issue(k, k.ravi, "WF-4").json()
    Loan.objects.filter(pk=overdue["id"]).update(due_on=k.today - dt.timedelta(days=1))
    assert issue(k, k.ravi, "WF-5").status_code == 422  # nothing new while something is overdue
    single = k.librarian.post(f"{C}/titles", {"title": "Malgudi Days", "copies": ["MD-1"]}, format="json").json()
    held = issue(k, k.meera, "MD-1").json()
    k.librarian.post(f"{C}/reservations", {"title": single["id"], "student": str(k.ravi.id)}, format="json")
    renewed = k.librarian.post(f"{C}/loans/{held['id']}/renew", {}, format="json")
    assert renewed.status_code == 409 and renewed.json()["code"] == "reserved"
    k.librarian.post(f"{C}/loans/{held['id']}/return", {}, format="json")
    assert Copy.objects.get(accession="MD-1").status == "reserved"
    Loan.objects.filter(student=k.ravi).update(status="returned")
    assert issue(k, k.meera, "MD-1").status_code == 409  # held for Ravi
    assert issue(k, k.ravi, "MD-1").status_code == 201


def test_transport_capacity_boarding_and_pickup(world, k, client_for):
    """TST-028 (transport)."""
    van = k.transport.post(f"{C}/vehicles", {"registration": "AP 16 1234", "capacity": 1}, format="json").json()
    route = k.transport.post(
        f"{C}/routes",
        {"name": "Lake Road", "vehicle": van["id"], "stops": [{"name": "Lake Road", "time": "07:40"}]},
        format="json",
    ).json()
    ride = {"route": route["id"], "stop": "Lake Road", "starts_on": "2026-06-01", "ends_on": "2026-12-31"}
    assert k.transport.post(f"{C}/riders", {**ride, "student": str(k.asha.id)}, format="json").status_code == 201
    full = k.transport.post(f"{C}/riders", {**ride, "student": str(k.ravi.id)}, format="json")
    assert full.status_code == 422 and full.json()["errors"][0]["field"] == "route"
    later = {**ride, "student": str(k.ravi.id), "starts_on": "2027-01-01", "ends_on": "2027-03-31"}
    assert k.transport.post(f"{C}/riders", later, format="json").status_code == 201
    twice = k.transport.post(
        f"{C}/riders", {**ride, "student": str(k.asha.id), "starts_on": "2026-09-01"}, format="json"
    )
    assert twice.status_code == 422
    driver = factories.member(world.a, role="teacher", username="driver")
    trip = k.transport.post(
        f"{C}/trips",
        {
            "route": route["id"],
            "date": str(k.today),
            "direction": "home",
            "driver": str(Membership.objects.get(user=driver).id),
        },
        format="json",
    ).json()
    me = client_for(world.a.slug, driver)
    assert me.post(f"{C}/trips/{trip['id']}/board", {"student": str(k.asha.id)}, format="json").status_code == 201
    assert me.post(f"{C}/trips/{trip['id']}/board", {"student": str(k.asha.id)}, format="json").status_code == 409
    stranger = me.post(
        f"{C}/trips/{trip['id']}/drop", {"student": str(k.asha.id), "handed_to": "Someone"}, format="json"
    )
    assert stranger.status_code == 422
    adult = Person.objects.create(institution=world.a, full_name="Lata Rao")
    parent = factories.user(username="asha.parent")
    Membership.objects.create(institution=world.a, user=parent, kind="guardian")
    GuardianLink.objects.create(
        institution=world.a,
        student=k.asha,
        adult=adult,
        user=parent,
        relationship="Mother",
        status="active",
        starts_on=dt.date(2026, 1, 1),
        access_record=True,
        source="staff",
    )
    assert (
        me.post(
            f"{C}/trips/{trip['id']}/drop", {"student": str(k.asha.id), "handed_to": "Lata Rao"}, format="json"
        ).status_code
        == 200
    )
    other = client_for(world.a.slug, factories.member(world.a, role="teacher", username="other"))
    assert other.post(f"{C}/trips/{trip['id']}/board", {"student": str(k.ravi.id)}, format="json").status_code == 404
    family = client_for(world.a.slug, parent)
    seen = family.get(f"/api/v1/family/children/{k.asha.id}/transport").json()
    assert (seen["route"], seen["stop"], seen["today"][0]["state"]) == ("Lake Road", "Lake Road", "planned")
    assert family.get(f"/api/v1/family/children/{k.ravi.id}/transport").status_code == 404


def test_hostel_beds_never_double_up(world, k, client_for):
    """TST-028 (hostel)."""
    hostel = k.warden.post(f"{C}/hostels", {"name": "Girls' hostel"}, format="json").json()
    bed = k.warden.post(f"{C}/hostels/{hostel['id']}/beds", {"room": "101", "label": "A"}, format="json").json()
    other_bed = k.warden.post(f"{C}/hostels/{hostel['id']}/beds", {"room": "102", "label": "A"}, format="json").json()
    stay = {"starts_on": "2026-06-01", "ends_on": "2027-03-31"}
    first = k.warden.post(f"{C}/allocations", {**stay, "student": str(k.asha.id)}, format="json").json()
    k.warden.post(f"{C}/allocations/{first['id']}/approve", {"bed": bed["id"]}, format="json")
    second = k.warden.post(f"{C}/allocations", {**stay, "student": str(k.meera.id)}, format="json").json()
    clash = k.warden.post(f"{C}/allocations/{second['id']}/approve", {"bed": bed["id"]}, format="json")
    assert clash.status_code == 422
    assert k.warden.post(f"{C}/allocations", {**stay, "student": str(k.asha.id)}, format="json").status_code == 422
    k.warden.post(f"{C}/allocations/{first['id']}/check-in", {}, format="json")
    moved = k.warden.post(f"{C}/allocations/{first['id']}/transfer", {"bed": other_bed["id"]}, format="json").json()
    assert moved["bed"]["room"] == "102" and moved["state"] == "allocated"
    assert (
        k.warden.post(f"{C}/allocations/{second['id']}/approve", {"bed": bed["id"]}, format="json").status_code == 200
    )
    occupancy = k.warden.get(f"{C}/hostels/{hostel['id']}").json()
    assert [(b["room"], b["resident"]) for b in occupancy["beds"]] == [("101", "Meera Iyer"), ("102", "Asha Rao")]
    from accounts.models import User

    login = User.objects.create_user(username="aster.2026-0001", password="x-Long-pass-1", full_name="Asha Rao")
    Membership.objects.create(institution=world.a, user=login, kind="student")
    k.asha.user = login
    k.asha.save()
    me = client_for(world.a.slug, login)
    asked = me.post(
        "/api/v1/student/campus/out-passes",
        {"leaves_at": "2026-11-01T10:00:00Z", "returns_at": "2026-11-02T18:00:00Z", "reason": "Family visit"},
        format="json",
    )
    assert asked.status_code == 201, asked.json()
    assert (
        k.warden.post(f"{C}/out-passes/{asked.json()['id']}/approve", {}, format="json").json()["state"] == "approved"
    )
    mine = me.get("/api/v1/student/campus").json()
    assert mine["hostel"]["bed"] == "102 A" and mine["out_passes"][0]["state"] == "approved"


def test_permissions_and_gates(world, k, client_for):
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.post(f"{C}/titles", {"title": "X", "copies": []}, format="json").status_code == 403
    assert k.librarian.post(f"{C}/vehicles", {"registration": "X", "capacity": 1}, format="json").status_code == 403
    switch_on(world.a, modules=("students", "fees"))
    assert k.librarian.get(f"{C}/titles").status_code == 404
