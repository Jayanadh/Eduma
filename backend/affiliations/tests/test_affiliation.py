"""University affiliation exchange (slice 5e; SCR-031, ACL §6)."""

import datetime as dt

import pytest

from academics.models import CourseAttempt, CurriculumVersion
from academics.tests import college as setup
from admissions.tests.conftest import switch_on
from affiliations.models import AffiliationGrant, SubmissionRow
from testing import factories

GRANTS = "/api/v1/institution/affiliations"
CONSOLE = "/api/v1/platform/affiliations"


@pytest.fixture
def pair(world, client_for):
    """Aster as a college with B.Sc students who sat Semester 1, and Summit University."""
    world.a.category = "college"
    world.a.save()
    switch_on(world.a, modules=("admissions", "students", "academics", "exams", "affiliations"))
    summit = factories.institution(slug="summit", display_name="Summit University", category="university")
    switch_on(summit, modules=("academics", "exams", "affiliations"))
    c = setup.build(world.a)
    for number, name, gp in (("2026-0001", "Asha Rao", 8), ("2026-0002", "Ravi Kumar", 6)):
        s = setup.student(c, number, name=name)
        CourseAttempt.objects.create(
            institution=world.a, enrollment=s.enrollments.get(), course=c.courses["PHY101"], attempt_no=1, term=c.term,
            credits=4, outcome="passed", grade_point=gp,
        )  # fmt: skip
    c.summit = summit
    c.console = client_for(None, world.platform_admin)
    c.college = client_for(world.a.slug, world.a_admin)
    c.registrar = client_for(summit.slug, factories.member(summit, username="summit.registrar"))
    return c


def propose(c, **changes):
    body = {
        "college": str(c.institution.id),
        "university": str(c.summit.id),
        "purpose": "Central examination of B.Sc results",
        "starts_on": str(c.today - dt.timedelta(days=1)),
        "ends_on": str(c.today + dt.timedelta(days=365)),
        "evidence": "Affiliation order 12/2026",
        **changes,
    }
    return c.console.post(CONSOLE, body, format="json")


def active_grant(c):
    grant = propose(c).json()
    return c.college.post(f"{GRANTS}/{grant['id']}/approve", {"version": grant["version"]}, format="json").json()


def build(c, grant):
    body = {"program": str(c.program.id), "term": str(c.term.id)}
    return c.college.post(f"{GRANTS}/{grant['id']}/batches", body, format="json")


def submit(c, batch):
    return c.college.post(f"{GRANTS}/batches/{batch['id']}/submit", {}, format="json")


def decide(c, batch, row, decision, reason=""):
    return c.registrar.post(
        f"{GRANTS}/received/{batch['id']}/rows/{row}", {"decision": decision, "reason": reason}, format="json"
    )


def test_a_grant_is_proposed_then_approved_by_the_college(world, pair, client_for):
    c = pair
    made = propose(c)
    assert made.status_code == 201, made.json()
    assert made.json()["status"] == "proposed" and made.json()["in_effect"] is False
    assert propose(c, university=str(world.b.id)).status_code == 422  # Birch is a college, not a university
    assert c.registrar.post(f"{GRANTS}/{made.json()['id']}/approve", {"version": 1}, format="json").status_code == 403
    approved = c.college.post(
        f"{GRANTS}/{made.json()['id']}/approve", {"version": made.json()["version"]}, format="json"
    )
    assert approved.json()["status"] == "active" and approved.json()["in_effect"] is True
    assert [(g["status"], g["side"]) for g in c.registrar.get(GRANTS).json()] == [("active", "university")]
    assert [g["side"] for g in c.college.get(GRANTS).json()] == ["college"]
    switch_on(world.b, modules=("academics", "exams", "affiliations"))
    assert client_for(world.b.slug, world.b_admin).get(GRANTS).json() == []


def test_a_batch_crosses_only_under_a_grant_in_effect(pair):
    c = pair
    proposed = propose(c).json()
    assert build(c, proposed).status_code == 409
    grant = active_grant(c)
    batch = build(c, grant)
    assert batch.status_code == 201, batch.json()
    batch = batch.json()
    assert [(r["number"], r["regulation"], r["problems"]) for r in batch["rows"]] == [
        ("2026-0001", "BSC-PHY R2026 rev 1", []),
        ("2026-0002", "BSC-PHY R2026 rev 1", []),
    ]
    assert batch["rows"][0]["attempts"] == [
        {
            "course": "PHY101",
            "title": "PHY101",
            "credits": "4.0",
            "attempt_no": 1,
            "outcome": "passed",
            "grade_point": "8.00",
        }
    ]
    assert c.registrar.get(f"{GRANTS}/received").json() == []  # drafts stay with the college
    assert [b["id"] for b in c.college.get(f"{GRANTS}/sent").json()] == [batch["id"]]
    sent = submit(c, batch)
    assert sent.status_code == 200 and sent.json()["status"] == "submitted"
    again = submit(c, batch)
    assert again.status_code == 200 and again.json()["revision"] == 1  # a retry keeps the batch as it is
    received = c.registrar.get(f"{GRANTS}/received").json()
    assert [(b["reference"], b["revision"], b["college"]) for b in received] == [
        (batch["reference"], 1, "Aster School")
    ]
    AffiliationGrant.objects.filter(pk=grant["id"]).update(ends_on=c.today - dt.timedelta(days=1))
    assert c.registrar.get(f"{GRANTS}/received").json() == []
    assert c.registrar.get(f"{GRANTS}/received/{batch['id']}").status_code == 404


def test_rows_with_problems_block_submitting(pair):
    c = pair
    grant = active_grant(c)
    CourseAttempt.objects.filter(enrollment__student__number="2026-0002").update(
        outcome="in_progress", grade_point=None
    )
    CurriculumVersion.objects.filter(pk=c.regulation.pk).update(status="draft")
    batch = build(c, grant).json()
    assert [len(r["problems"]) for r in batch["rows"]] == [1, 2]
    refused = submit(c, batch)
    assert refused.status_code == 422
    for row in batch["rows"]:
        c.college.delete(f"{GRANTS}/batches/{batch['id']}/rows/{row['id']}")
    assert submit(c, batch).status_code == 422  # nothing left to send


def test_review_correction_and_history(pair):
    c = pair
    grant = active_grant(c)
    batch = build(c, grant).json()
    submit(c, batch)
    asha, ravi = (r["id"] for r in batch["rows"])
    assert decide(c, batch, ravi, "rejected").status_code == 422  # a reason is needed
    assert decide(c, batch, asha, "accepted").status_code == 200
    reviewed = decide(c, batch, ravi, "rejected", "Grade point does not match the mark sheet").json()
    assert reviewed["status"] == "reviewed"
    mine = c.college.get(f"{GRANTS}/batches/{batch['id']}").json()
    assert {r["number"]: (r["status"], r["reason"]) for r in mine["rows"]} == {
        "2026-0001": ("accepted", ""),
        "2026-0002": ("rejected", "Grade point does not match the mark sheet"),
    }
    CourseAttempt.objects.filter(enrollment__student__number="2026-0002").update(grade_point=7)
    second = c.college.post(f"{GRANTS}/batches/{batch['id']}/revise", {"corrections": [asha]}, format="json").json()
    assert (second["reference"], second["revision"]) == (batch["reference"], 2)
    rows = {r["number"]: r for r in second["rows"]}
    assert rows["2026-0002"]["attempts"][0]["grade_point"] == "7.00" and not rows["2026-0002"]["is_correction"]
    assert rows["2026-0001"]["is_correction"]
    submit(c, second)
    for row in second["rows"]:
        decide(c, second, row["id"], "accepted")
    shown = c.registrar.get(f"{GRANTS}/received/{second['id']}").json()
    assert {r["number"]: r["current"] for r in shown["rows"]} == {"2026-0001": True, "2026-0002": True}
    first = c.registrar.get(f"{GRANTS}/received/{batch['id']}").json()
    assert {r["number"]: r["current"] for r in first["rows"]} == {"2026-0001": False, "2026-0002": False}
    assert SubmissionRow.objects.count() == 4  # history kept


def test_revoking_stops_both_sides(pair):
    c = pair
    grant = active_grant(c)
    batch = build(c, grant).json()
    submit(c, batch)
    revoked = c.registrar.post(
        f"{GRANTS}/{grant['id']}/revoke", {"version": grant["version"], "reason": "Affiliation ended"}, format="json"
    )
    assert revoked.json()["status"] == "revoked"
    assert c.registrar.get(f"{GRANTS}/received/{batch['id']}").status_code == 404
    assert build(c, grant).status_code == 409
    assert decide(c, batch, batch["rows"][0]["id"], "accepted").status_code == 404


def test_only_the_platform_proposes(world, pair, client_for):
    c = pair
    assert c.college.post(CONSOLE, {}, format="json").status_code in (403, 404)
    assert client_for(None, world.a_admin).get(CONSOLE).status_code == 403
