"""Placements, internships, alumni, research and quality evidence (slice 10c S10C-05..09)."""

import datetime as dt

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from academics.models import CourseAttempt
from academics.tests import college as setup
from accounts.models import Membership, User
from accounts.permissions import today_for
from admissions.tests.conftest import switch_on
from testing import factories

D, ST = "/api/v1/development", "/api/v1/student"
PDF = b"%PDF-1.4\n% evidence\n"


def login(world, client_for, student):
    user = User.objects.create_user(
        username=f"aster.{student.number}", password="x-Long-pass-1", full_name=student.person.full_name
    )
    Membership.objects.create(institution=world.a, user=user, kind="student")
    student.user = user
    student.save()
    return client_for(world.a.slug, user)


@pytest.fixture
def d(world, client_for):
    world.a.category = "college"
    world.a.save()
    switch_on(world.a, modules=("students", "academics", "placements", "quality"))
    c = setup.build(world.a)
    ns = type("D", (), {})()
    ns.c, ns.today = c, today_for(world.a)
    ns.asha_student = setup.student(c, "2026-0001", name="Asha Rao")
    ns.ravi_student = setup.student(c, "2026-0002", name="Ravi Kumar")
    CourseAttempt.objects.create(
        institution=world.a, enrollment=ns.asha_student.enrollments.get(), course=c.courses["MAT101"], attempt_no=1,
        term=c.term, credits=3, outcome="passed", grade_point=8,
    )  # fmt: skip
    ns.asha, ns.ravi = login(world, client_for, ns.asha_student), login(world, client_for, ns.ravi_student)
    member = lambda role, username, name="": client_for(  # noqa: E731
        world.a.slug, factories.member(world.a, role=role, username=username, full_name=name or username)
    )
    ns.office = member("placement_officer", "placement")
    ns.research = member("research_coordinator", "research")
    ns.iqac = member("iqac_coordinator", "iqac")
    ns.mentor = member("teacher", "mentor", "Dr. Mentor")
    ns.other = member("teacher", "other")
    ns.owner = member("teacher", "hod.cs", "Head of CS")
    return ns


def post(client, url, body=None):
    return client.post(url, body or {}, format="json")


def opportunities(d):
    employer = post(d.office, f"{D}/employers", {"name": "Infosys"}).json()
    soon = (d.today + dt.timedelta(days=10)).isoformat()
    intern = {"employer": employer["id"], "kind": "internship", "title": "Summer analyst", "programs": [str(d.c.program.id)],
              "min_cgpa": "7.50", "closes_on": soon}  # fmt: skip
    job = {"employer": employer["id"], "kind": "job", "title": "Graduate engineer", "closes_on": soon}
    return post(d.office, f"{D}/opportunities", intern).json(), post(d.office, f"{D}/opportunities", job).json()


def test_placements_need_consent_and_eligibility_and_count_offers_apart(d):
    intern, job = opportunities(d)
    ravi_sees = {o["title"]: o["eligibility"] for o in d.ravi.get(f"{ST}/placements").json()["opportunities"]}
    assert ravi_sees["Summer analyst"]["reasons"] == ["Needs a CGPA of 7.50."]
    assert post(d.ravi, f"{ST}/placements/{intern['id']}/apply", {"consent": True}).status_code == 422
    assert post(d.asha, f"{ST}/placements/{intern['id']}/apply", {"consent": False}).status_code == 422
    applied = post(d.asha, f"{ST}/placements/{intern['id']}/apply", {"consent": True})
    assert applied.status_code == 201, applied.json()
    assert post(d.asha, f"{ST}/placements/{intern['id']}/apply", {"consent": True}).status_code == 409
    [row] = d.office.get(f"{D}/opportunities/{intern['id']}/applications").json()
    assert (row["student"]["name"], row["eligibility"]["cgpa"], row["eligibility"]["program"]) == (
        "Asha Rao",
        "8.00",
        "BSC-PHY",
    )
    assert post(d.asha, f"{D}/applications/{row['id']}/state", {"state": "offered"}).status_code == 403
    assert post(d.office, f"{D}/applications/{row['id']}/state", {"state": "accepted"}).status_code == 422
    post(d.office, f"{D}/applications/{row['id']}/state", {"state": "shortlisted"})
    post(d.office, f"{D}/applications/{row['id']}/state", {"state": "offered"})
    accepted = post(d.asha, f"{ST}/placement-applications/{row['id']}/decide", {"decision": "accept"})
    assert accepted.json()["state"] == "accepted"
    post(d.asha, f"{ST}/placements/{job['id']}/apply", {"consent": True})
    [job_row] = d.office.get(f"{D}/opportunities/{job['id']}/applications").json()
    post(d.office, f"{D}/applications/{job_row['id']}/state", {"state": "offered"})
    post(d.asha, f"{ST}/placement-applications/{job_row['id']}/decide", {"decision": "decline"})
    counts = {
        r["opportunity"]: (r["applied"], r["offers"], r["accepted"])
        for r in d.office.get(f"{D}/placement-report").json()
    }
    assert counts == {"Summer analyst": (1, 1, 1), "Graduate engineer": (1, 1, 0)}
    assert d.mentor.get(f"{D}/placement-report").status_code == 403


def test_internship_is_evaluated_by_its_supervisor(d):
    intern, _ = opportunities(d)
    post(d.asha, f"{ST}/placements/{intern['id']}/apply", {"consent": True})
    [row] = d.office.get(f"{D}/opportunities/{intern['id']}/applications").json()
    post(d.office, f"{D}/applications/{row['id']}/state", {"state": "offered"})
    post(d.asha, f"{ST}/placement-applications/{row['id']}/decide", {"decision": "accept"})
    [internship] = d.office.get(f"{D}/internships").json()
    post(d.office, f"{D}/internships/{internship['id']}/supervisor", {"username": "mentor"})
    review = {"score": "86", "remarks": "Built the reporting dashboard."}
    assert post(d.other, f"{D}/internships/{internship['id']}/evaluate", review).status_code == 403
    assert d.other.get(f"{D}/internships").json() == []
    done = post(d.mentor, f"{D}/internships/{internship['id']}/evaluate", review).json()
    assert (done["supervisor"], done["score"]) == ("Dr. Mentor", "86.00")


def test_alumni_are_listed_only_while_they_consent(d):
    assert d.asha.put(f"{ST}/alumni", {"consent": False, "email": "asha@example.com"}, format="json").status_code == 422
    d.asha.put(f"{ST}/alumni", {"consent": True, "email": "asha@example.com", "occupation": "Analyst"}, format="json")
    assert [a["email"] for a in d.office.get(f"{D}/alumni").json()] == ["asha@example.com"]
    assert d.asha.delete(f"{ST}/alumni").status_code == 204
    assert d.office.get(f"{D}/alumni").json() == []


def test_research_ethics_and_supervision(d):
    body = {"student": str(d.asha_student.id), "topic": "Rural broadband adoption", "started_on": "2026-07-01"}
    scholar = post(d.research, f"{D}/scholars", body).json()
    url = f"{D}/scholars/{scholar['id']}"
    post(d.research, f"{url}/supervisors", {"username": "mentor"})
    due = (d.today + dt.timedelta(days=60)).isoformat()
    post(d.research, f"{url}/milestones", {"title": "Field survey", "due_on": due, "needs_ethics": True})
    mine = d.asha.get(f"{ST}/research").json()
    survey = mine["milestones"][0]["id"]
    submit = f"{ST}/research/milestones/{survey}/submit"
    refused = post(d.asha, submit, {"summary": "Survey of 120 households"})
    assert refused.status_code == 409 and refused.json()["code"] == "ethics_required"
    year_ago = d.today - dt.timedelta(days=400)
    expired = {"reference": "IEC/2025/7", "committee": "Ethics committee", "valid_from": year_ago.isoformat(),
               "valid_to": (year_ago + dt.timedelta(days=30)).isoformat()}  # fmt: skip
    post(d.research, f"{url}/ethics", expired)
    assert post(d.asha, submit, {"summary": "Survey"}).status_code == 409
    current = {**expired, "reference": "IEC/2026/3", "valid_from": d.today.isoformat(),
               "valid_to": (d.today + dt.timedelta(days=365)).isoformat()}  # fmt: skip
    post(d.research, f"{url}/ethics", current)
    assert post(d.asha, submit, {"summary": "Survey"}).json()["milestones"][0]["state"] == "submitted"
    assert post(d.asha, f"{D}/milestones/{survey}/approve").status_code == 403  # the scholar is not staff
    assert post(d.research, f"{D}/milestones/{survey}/approve").status_code == 404  # not a supervisor
    assert post(d.mentor, f"{D}/milestones/{survey}/approve").json()["milestones"][0]["state"] == "approved"
    assert d.other.get(url).status_code == 404 and d.other.get(f"{D}/scholars").json() == []
    assert d.mentor.get(url).status_code == 200
    supervision = d.research.get(url).json()["supervisors"][0]["id"]
    post(d.research, f"{D}/supervisions/{supervision}/end")
    assert d.mentor.get(url).status_code == 404  # access ends with the supervision


def test_quality_evidence_versions_and_freeze(d):
    cycle = post(d.iqac, f"{D}/cycles", {"framework": "NAAC", "period": "2025-26"}).json()
    url = f"{D}/cycles/{cycle['id']}"
    post(d.iqac, f"{url}/requests", {"criterion": "3.2.1", "title": "Papers per teacher", "username": "hod.cs"})
    assert post(d.iqac, f"{url}/freeze").status_code == 422
    [request] = d.owner.get(f"{D}/evidence").json()
    upload = f"{D}/evidence/{request['id']}/upload"
    bad = d.owner.post(upload, {"file": SimpleUploadedFile("list.pdf", b"just text", "application/pdf")}, format="multipart")
    assert bad.status_code == 422
    assert d.owner.get(f"{D}/evidence").json()[0]["versions"] == []  # a failed upload records nothing
    first = d.owner.post(upload, {"file": SimpleUploadedFile("papers.pdf", PDF, "application/pdf")}, format="multipart")
    assert first.status_code == 200, first.json()
    first = first.json()
    assert (first["state"], len(first["versions"][0]["sha256"])) == ("submitted", 64)
    assert post(d.owner, f"{D}/evidence/{request['id']}/accept").status_code == 403
    post(d.iqac, f"{D}/evidence/{request['id']}/return", {"note": "Add the 2025 papers"})
    d.owner.post(upload, {"file": SimpleUploadedFile("papers-2.pdf", PDF + b"2025", "application/pdf")}, format="multipart")
    assert post(d.iqac, f"{D}/evidence/{request['id']}/accept").json()["state"] == "accepted"
    frozen = post(d.iqac, f"{url}/freeze").json()
    assert frozen["frozen_at"] and len(frozen["snapshot_hash"]) == 64
    exported = d.iqac.get(f"{url}/export").json()
    versions = d.iqac.get(url).json()["requests"][0]["versions"]
    assert exported["evidence"] == [{"criterion": "3.2.1", "title": "Papers per teacher", "owner": "Head of CS",
                                     "version": 2, "sha256": versions[1]["sha256"]}]  # fmt: skip
    assert exported["snapshot_sha256"] == frozen["snapshot_hash"]
    late = d.owner.post(upload, {"file": SimpleUploadedFile("late.pdf", PDF, "application/pdf")}, format="multipart")
    assert late.status_code == 409
    assert d.owner.get(f"{D}/evidence-files/{versions[0]['id']}").status_code == 200
    assert d.other.get(f"{D}/evidence-files/{versions[0]['id']}").status_code == 404


def test_module_gates_and_isolation(world, d, client_for):
    intern, _ = opportunities(d)
    switch_on(world.b, modules=("placements",))
    assert (
        client_for(world.b.slug, world.b_admin).get(f"{D}/opportunities/{intern['id']}/applications").status_code == 404
    )
    switch_on(world.a, modules=("students", "academics"))
    assert d.office.get(f"{D}/employers").status_code == 404
    assert d.asha.get(f"{ST}/placements").status_code == 404
