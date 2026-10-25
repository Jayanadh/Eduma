"""Service requests and grievances (slice 10c; TST-034)."""

import datetime as dt

import pytest
from django.utils import timezone

from academics.tests.conftest import enrolled_student
from accounts.models import Membership, User
from admissions.tests.conftest import switch_on
from cases.models import Resolution
from communication.models import Notification
from testing import factories

C = "/api/v1/service-cases"


@pytest.fixture
def g(world, client_for):
    switch_on(world.a, modules=("students", "services"))
    ns = type("G", (), {})()
    asha = enrolled_student(world.a, "2026-0001", name="Asha Rao")
    login = User.objects.create_user(username="aster.2026-0001", password="x-Long-pass-1", full_name="Asha Rao")
    Membership.objects.create(institution=world.a, user=login, kind="student")
    asha.user = login
    asha.save()
    ns.asha_user = login
    ns.asha = client_for(world.a.slug, login)
    ns.triage = client_for(world.a.slug, factories.member(world.a, role="student_services", username="desk"))
    ns.officer_user = factories.member(world.a, role="grievance_officer", username="grievance.one", full_name="G One")
    ns.officer = client_for(world.a.slug, ns.officer_user)
    ns.second_user = factories.member(world.a, role="grievance_officer", username="grievance.two", full_name="G Two")
    ns.second = client_for(world.a.slug, ns.second_user)
    ns.teacher_user = factories.member(world.a, role="teacher", username="teacher", full_name="Kavya Nair")
    ns.teacher = client_for(world.a.slug, ns.teacher_user)
    ns.admin = client_for(world.a.slug, world.a_admin)
    return ns


def post(client, url, body=None):
    return client.post(url, body or {}, format="json")


def open_grievance(g):
    body = {
        "case_type": "grievance",
        "subject": "Marks for my maths internal",
        "description": "My internal was entered as 12; my answer sheet shows 22.",
        "assignee": "ignored",
        "state": "resolved",
    }
    made = post(g.asha, f"{C}/", body)
    assert made.status_code == 201, made.json()
    return made.json()


def membership(user):
    return str(Membership.objects.get(user=user).id)


def test_tst034_each_person_sees_only_what_they_may(g):
    case = open_grievance(g)
    assert (case["number"], case["state"], case["confidential"]) == ("SC-0001", "submitted", True)
    url = f"{C}/{case['id']}"
    shell = g.triage.get(url).json()
    assert shell["seen_as"] == "triage" and "subject" not in shell and "description" not in shell
    assert g.triage.get(f"{C}/", {"search": "maths"}).json() == []  # confidential subjects aren't searchable
    assert g.teacher.get(url).status_code == 404 and g.teacher.get(f"{C}/").json() == []
    assert g.admin.get(url).json()["seen_as"] == "triage"  # an admin role alone discloses nothing
    officers = [o["name"] for o in g.triage.get(f"{url}/officers").json()]
    assert "G One" in officers and "Kavya Nair" not in officers
    refused = post(g.triage, f"{url}/assign", {"assignee": membership(g.teacher_user)})
    assert refused.status_code == 422  # not allowed confidential cases
    post(g.triage, f"{url}/assign", {"assignee": membership(g.officer_user)})
    assert Notification.objects.filter(user=g.officer_user, text__contains="SC-0001").exists()
    post(
        g.officer, f"{url}/notes", {"text": "Requested the answer sheet from the exam cell.", "visibility": "internal"}
    )
    post(g.officer, f"{url}/notes", {"text": "We are checking your answer sheet."})
    officer_view = g.officer.get(url).json()
    assert [n["visibility"] for n in officer_view["notes"]] == ["internal", "requester_visible"]
    assert officer_view["requester"] == "Asha Rao" and officer_view["subject"].startswith("Marks")
    mine = g.asha.get(url).json()
    assert [n["text"] for n in mine["notes"]] == ["We are checking your answer sheet."]
    assert "assignee" not in mine and "due_at" not in mine
    assert "exam cell" not in g.asha.get(f"{C}/").content.decode()
    update = Notification.objects.get(user=g.asha_user)
    assert update.text == "There's an update on SC-0001."  # never an excerpt
    assert update.link == f"/cases/{case['id']}"
    assert post(g.asha, f"{url}/notes", {"text": "x", "visibility": "internal"}).status_code == 403
    assert post(g.triage, f"{url}/notes", {"text": "x"}).status_code == 403
    post(g.triage, f"{url}/assign", {"assignee": membership(g.second_user)})
    after = g.officer.get(url).json()  # reassignment removes the old access: back to triage's shell
    assert after["seen_as"] == "triage" and "notes" not in after and "subject" not in after
    assert "Requested the answer sheet" not in g.officer.get(f"{C}/").content.decode()
    assert g.second.get(url).json()["seen_as"] == "officer"


def test_tst034_appeal_keeps_the_first_resolution(g):
    case = open_grievance(g)
    url = f"{C}/{case['id']}"
    post(g.triage, f"{url}/assign", {"assignee": membership(g.officer_user)})
    assert post(g.asha, f"{url}/resolve", {"text": "x"}).status_code == 403
    resolved = post(g.officer, f"{url}/resolve", {"text": "The internal is corrected to 22."}).json()
    assert resolved["state"] == "resolved"
    assert g.asha.get(url).json()["can_appeal"] is True
    assert post(g.officer, f"{url}/appeals", {"reason": "x"}).status_code == 403
    appealed = post(g.asha, f"{url}/appeals", {"reason": "The final mark wasn't recalculated."})
    assert appealed.status_code == 201 and appealed.json()["state"] == "appealed"
    assert g.officer.get(url).json()["seen_as"] == "triage"  # back with triage, not the first officer
    assert post(g.triage, f"{url}/assign", {"assignee": membership(g.officer_user)}).status_code == 422
    post(g.triage, f"{url}/assign", {"assignee": membership(g.second_user)})
    post(g.second, f"{url}/resolve", {"text": "Final mark recalculated: B to A."})
    final = g.asha.get(url).json()
    assert [(r["stage"], r["text"]) for r in final["resolutions"]] == [
        ("original", "The internal is corrected to 22."),
        ("appeal", "Final mark recalculated: B to A."),
    ]
    assert final["can_appeal"] is False
    again = post(g.asha, f"{url}/appeals", {"reason": "Once more"})
    assert again.status_code == 409 and again.json()["code"] == "appeal_used"


def test_appeals_close_after_15_days(g):
    case = open_grievance(g)
    url = f"{C}/{case['id']}"
    post(g.triage, f"{url}/assign", {"assignee": membership(g.officer_user)})
    post(g.officer, f"{url}/resolve", {"text": "Corrected."})
    Resolution.objects.update(at=timezone.now() - dt.timedelta(days=16))
    late = post(g.asha, f"{url}/appeals", {"reason": "Late"})
    assert late.status_code == 409 and late.json()["code"] == "appeal_closed"


def test_ordinary_requests_are_searchable_by_triage_and_go_to_any_staff(world, g):
    body = {"case_type": "service_request", "subject": "Bonafide certificate", "description": "For a visa."}
    made = post(g.teacher, f"{C}/", body)
    case = made.json()
    assert case["confidential"] is False
    found = g.triage.get(f"{C}/", {"search": "bonafide"}).json()
    assert [c["subject"] for c in found] == ["Bonafide certificate"]
    office = factories.member(world.a, role="teacher", username="office", full_name="Front Office")
    assigned = post(g.triage, f"{C}/{case['id']}/assign", {"assignee": membership(office)}).json()
    assert assigned["assignee"] == "Front Office"
    assert (
        post(g.triage, f"{C}/{case['id']}/assign", {"assignee": membership(g.teacher_user)}).status_code == 422
    )  # own


def test_module_gate_and_isolation(world, g, client_for):
    case = open_grievance(g)
    switch_on(world.b, modules=("services",))
    assert client_for(world.b.slug, world.b_admin).get(f"{C}/{case['id']}").status_code == 404
    switch_on(world.a, modules=("students",))
    assert g.asha.get(f"{C}/").status_code == 404
