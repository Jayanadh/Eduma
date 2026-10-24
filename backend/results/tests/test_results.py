"""Assessments, results, documents and outcomes (slice 7; TST-012, TST-014, EX-02)."""

import pytest

from academics import offerings, registration
from academics.models import CourseAttempt
from academics.tests import college as setup
from accounts.models import Membership
from admissions.tests.conftest import switch_on
from results.models import Candidate, ResultVersion
from testing import factories

R = "/api/v1/institution/results"
BANDS = [
    {"min": "90", "grade": "O", "point": "10"},
    {"min": "75", "grade": "A", "point": "8"},
    {"min": "60", "grade": "B", "point": "7"},
    {"min": "40", "grade": "C", "point": "5"},
    {"min": "0", "grade": "F", "point": "0"},
]


@pytest.fixture
def c(world, client_for):
    world.a.category = "college"
    world.a.save()
    switch_on(world.a, modules=("admissions", "students", "academics", "attendance", "exams", "outcomes"))
    c = setup.build(world.a)
    c.admin = client_for(world.a.slug, world.a_admin)
    c.students = [setup.student(c, f"2026-000{n}", name=name) for n, name in ((1, "Asha Rao"), (2, "Ravi Kumar"))]
    c.maths.capacity = 5
    c.maths.save()
    for s in c.students:
        registration.register(world.a_admin, s, [c.maths.id])
    teacher = factories.member(world.a, role="teacher", username="maths.teacher")
    offerings.assign_teacher(world.a_admin, c.maths, Membership.objects.get(user=teacher).id)
    c.teacher = client_for(world.a.slug, teacher)
    c.moderator = client_for(world.a.slug, factories.member(world.a, role="exam_officer", username="exam.one"))
    c.publisher = client_for(world.a.slug, factories.member(world.a, role="exam_officer", username="exam.two"))
    return c


def scheme(client, **changes):
    body = {
        "name": "Theory 40/60", "pass_percent": "40", "decimals": 2, "bands": BANDS,
        "components": [
            {"name": "Internal", "max_marks": "40", "weight": "40"},
            {"name": "Final", "max_marks": "60", "weight": "60", "min_percent": "40"},
        ],
        **changes,
    }  # fmt: skip
    made = client.post(f"{R}/schemes", body, format="json").json()
    return client.post(f"{R}/schemes/{made['id']}/publish", {"version": made["version"]}, format="json").json()


def assessment(c, published):
    body = {
        "scheme": published["id"],
        "term": str(c.term.id),
        "offering": str(c.maths.id),
        "title": "MAT101 end of term",
    }
    return c.admin.post(f"{R}/assessments", body, format="json").json()


def enter(client, a, rows):
    """rows: {student number: (internal, final)} with a number or a status word for each."""
    components = {comp["name"]: comp["id"] for comp in a["scheme"]["components"]}
    marks = []
    for cand in a["candidates"]:
        for name, value in zip(("Internal", "Final"), rows[cand["student"]["number"]], strict=True):
            if value is None:
                continue
            item = {"candidate": cand["id"], "component": components[name]}
            item.update({"status": value} if isinstance(value, str) else {"status": "scored", "score": str(value)})
            marks.append(item)
    return client.post(f"{R}/assessments/{a['id']}/marks", {"version": a["version"], "marks": marks}, format="json")


def step(client, a, action, **body):
    current = client.get(f"{R}/assessments/{a['id']}").json()
    return client.post(f"{R}/assessments/{a['id']}/{action}", {"version": current["version"], **body}, format="json")


def results(client, a):
    shown = client.get(f"{R}/assessments/{a['id']}").json()
    return {cand["student"]["number"]: cand["result"] for cand in shown["candidates"]}


def through(c, a, rows):
    enter(c.teacher, a, rows)
    step(c.teacher, a, "submit")
    step(c.moderator, a, "moderate")
    return step(c.publisher, a, "publish")


def test_ex02_weighted_total_and_component_minimum(c):
    """TST-012: 32/40 + 45/60 = 77; a failed component minimum fails a passing total."""
    a = assessment(c, scheme(c.admin))
    published = through(c, a, {"2026-0001": (32, 45), "2026-0002": (40, 20)})
    assert published.status_code == 200, published.json()
    shown = results(c.admin, a)
    asha, ravi = shown["2026-0001"], shown["2026-0002"]
    assert (asha["total"], asha["grade"], asha["grade_point"], asha["outcome"]) == ("77.00", "A", "8.00", "passed")
    assert (ravi["total"], ravi["outcome"], ravi["grade"], ravi["failed_components"]) == (
        "60.00",
        "failed",
        "F",
        ["Final"],
    )


def test_absent_withheld_and_exempt_are_not_zero(c):
    a = assessment(c, scheme(c.admin))
    through(c, a, {"2026-0001": ("absent", 50), "2026-0002": ("exempt", 45)})
    shown = results(c.admin, a)
    assert (shown["2026-0001"]["outcome"], shown["2026-0001"]["total"]) == ("absent", None)
    assert shown["2026-0002"]["total"] == "75.00"  # 45/60 × 60, scaled to 100 without the exempt internal
    attempt = CourseAttempt.objects.get(enrollment__student=c.students[0])
    assert (attempt.outcome, attempt.grade_point) == ("absent", None)


def test_missing_marks_block_publishing(c):
    a = assessment(c, scheme(c.admin))
    enter(c.teacher, a, {"2026-0001": (32, 45), "2026-0002": (40, None)})
    step(c.teacher, a, "submit")
    step(c.moderator, a, "moderate")
    refused = step(c.publisher, a, "publish")
    assert refused.status_code == 409 and refused.json()["code"] == "missing_marks"


def test_who_does_what(world, c, client_for):
    """TST-014: the maker can't publish; the submitter can't moderate; published marks don't change."""
    a = assessment(c, scheme(c.admin))
    enter(c.teacher, a, {"2026-0001": (32, 45), "2026-0002": (30, 40)})
    assert step(c.teacher, a, "publish").status_code == 403
    step(c.teacher, a, "submit")
    assert enter(c.teacher, a, {"2026-0001": (1, 1), "2026-0002": (1, 1)}).status_code == 409
    returned = step(c.moderator, a, "return", reason="Check Ravi's final")
    assert returned.json()["state"] == "draft"
    enter(c.teacher, c.teacher.get(f"{R}/assessments/{a['id']}").json(), {"2026-0001": (32, 45), "2026-0002": (30, 42)})
    step(c.moderator, a, "submit")
    assert step(c.moderator, a, "moderate").status_code == 403  # submitted it themselves
    step(c.publisher, a, "moderate")
    step(c.moderator, a, "publish")
    assert (
        enter(
            c.moderator, c.admin.get(f"{R}/assessments/{a['id']}").json(), {"2026-0001": (1, 1), "2026-0002": (1, 1)}
        ).status_code
        == 409
    )
    other = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert other.get(f"{R}/assessments/{a['id']}").status_code == 404


def test_revaluation_adds_a_revision(c):
    """TST-014: an approved correction is a new revision; the old one stays reproducible."""
    a = assessment(c, scheme(c.admin))
    through(c, a, {"2026-0001": (32, 45), "2026-0002": (30, 42)})
    cand = Candidate.objects.get(enrollment__student=c.students[0])
    final = next(comp["id"] for comp in a["scheme"]["components"] if comp["name"] == "Final")
    case = c.moderator.post(
        f"{R}/candidates/{cand.id}/cases",
        {"reason": "Recount found 3 missed marks", "marks": {final: {"status": "scored", "score": "48"}}},
        format="json",
    )
    assert case.status_code == 201, case.json()
    assert c.moderator.post(f"{R}/cases/{case.json()['id']}/approve", {}, format="json").status_code == 403
    approved = c.publisher.post(f"{R}/cases/{case.json()['id']}/approve", {}, format="json")
    assert approved.json()["state"] == "approved"
    versions = list(ResultVersion.objects.filter(candidate=cand))
    assert [(v.revision, v.shown_total, v.superseded_at is not None) for v in versions] == [
        (1, "77.00", True),
        (2, "80.00", False),
    ]
    assert versions[0].inputs != versions[1].inputs and versions[0].inputs_hash != versions[1].inputs_hash
    assert results(c.admin, a)["2026-0001"]["revision"] == 2
    assert CourseAttempt.objects.get(enrollment__student=c.students[0]).grade_point == 8


def test_schemes_are_checked_and_frozen(c):
    bad = c.admin.post(
        f"{R}/schemes",
        {"name": "Bad", "bands": BANDS, "components": [{"name": "Only", "max_marks": "50", "weight": "60"}]},
        format="json",
    ).json()
    assert (
        c.admin.post(f"{R}/schemes/{bad['id']}/publish", {"version": bad["version"]}, format="json").status_code == 422
    )
    published = scheme(c.admin)
    patched = c.admin.patch(
        f"{R}/schemes/{published['id']}", {"version": published["version"], "name": "X"}, format="json"
    )
    assert patched.status_code == 409
    revised = c.admin.post(f"{R}/schemes/{published['id']}/revise", {}, format="json").json()
    assert (revised["revision"], revised["status"], len(revised["components"])) == (2, "draft", 2)


def test_transcript_award_and_public_verification(world, c, client_for):
    a = assessment(c, scheme(c.admin))
    through(c, a, {"2026-0001": (32, 45), "2026-0002": (30, 42)})
    asha = c.students[0]
    made = c.publisher.post(f"{R}/students/{asha.id}/documents", {"kind": "transcript"}, format="json")
    assert made.status_code == 201, made.json()
    doc = made.json()
    assert doc["content"]["cgpa"] == "8.00" and doc["number"].startswith("TR-")
    public = client_for(world.a.slug)
    seen = public.get(f"/api/v1/public/verify/{doc['token']}").json()
    assert seen == {
        "institution": "Aster School",
        "kind": "Transcript",
        "number": doc["number"],
        "issued_on": seen["issued_on"],
        "holder": "A. Rao",
        "status": "current",
        "superseded_by": None,
    }
    again = c.publisher.post(f"{R}/students/{asha.id}/documents", {"kind": "transcript"}, format="json").json()
    assert public.get(f"/api/v1/public/verify/{doc['token']}").json()["status"] == "superseded"
    assert public.get(f"/api/v1/public/verify/{doc['token']}").json()["superseded_by"] == again["number"]
    short = c.publisher.post(f"{R}/students/{asha.id}/documents", {"kind": "award"}, format="json")
    assert short.status_code == 422  # 3 of 12 credits
    award = c.publisher.post(
        f"{R}/students/{asha.id}/documents", {"kind": "award", "exception": "Board decision 4/2026"}, format="json"
    )
    assert award.status_code == 201 and award.json()["content"]["qualification"] == "B.Sc"
    revoked = c.publisher.post(
        f"{R}/documents/{award.json()['id']}/revoke", {"reason": "Issued in error"}, format="json"
    )
    assert revoked.json()["status"] == "revoked"
    assert public.get(f"/api/v1/public/verify/{award.json()['token']}").json()["status"] == "revoked"
    assert public.get("/api/v1/public/verify/not-a-token").status_code == 404
    denied = c.teacher.post(f"{R}/students/{asha.id}/documents", {"kind": "transcript"}, format="json")
    assert denied.status_code == 404  # the record isn't visible to a teacher at all


def test_outcome_attainment(c):
    a = assessment(c, scheme(c.admin))
    co = c.admin.post(
        f"{R}/courses/{c.courses['MAT101'].id}/outcomes", {"code": "CO1", "description": "Differentiate"}, format="json"
    ).json()
    final = next(comp["id"] for comp in a["scheme"]["components"] if comp["name"] == "Final")
    assert (
        c.admin.post(
            f"{R}/assessments/{a['id']}/mappings", {"component": final, "outcome": co["id"]}, format="json"
        ).status_code
        == 201
    )
    through(c, a, {"2026-0001": (32, 45), "2026-0002": (30, 30)})
    run = c.admin.post(f"{R}/assessments/{a['id']}/attainment", {"threshold_percent": "60"}, format="json")
    assert run.status_code == 201, run.json()
    assert run.json()["results"] == [{"outcome": "CO1", "candidates": 2, "attained": 1, "percent": "50.0"}]
