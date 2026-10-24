"""School report cards: published subject results, attendance and the promotion decision (slice 7 S7-09, S7-10)."""

import datetime as dt

from academics.models import Section, Term
from academics.tests.conftest import enrolled_student, on, school  # noqa: F401 — fixtures
from academics.tests.test_placement import place
from admissions.tests.conftest import switch_on
from testing import factories

R = "/api/v1/institution/results"


def test_a_report_card_shows_published_subjects_and_the_promotion(world, client_for, school):  # noqa: F811
    switch_on(world.a, modules=("admissions", "students", "academics", "attendance", "exams", "report_cards"))
    admin = client_for(world.a.slug, world.a_admin)
    term = Term.objects.create(
        year=school.year, name="Term 1", ordinal=1, starts_on=dt.date(2026, 6, 1), ends_on=dt.date(2026, 10, 31)
    )
    section = Section.objects.create(
        institution=world.a, year=school.year, grade=school.c6, campus=school.main, code="6A", capacity=40
    )
    kiran = enrolled_student(world.a, "2026-0001", name="Kiran Rao")
    place(admin, section, kiran)
    made = admin.post(
        f"{R}/schemes",
        {
            "name": "Term test",
            "bands": [{"min": "50", "grade": "A", "point": "8"}, {"min": "0", "grade": "B", "point": "6"}],
            "components": [{"name": "Test", "max_marks": "50", "weight": "100"}],
        },
        format="json",
    ).json()
    scheme = admin.post(f"{R}/schemes/{made['id']}/publish", {"version": made["version"]}, format="json").json()
    a = admin.post(
        f"{R}/assessments",
        {
            "scheme": scheme["id"],
            "term": str(term.id),
            "section": str(section.id),
            "subject": str(school.science.id),
            "title": "Science term test",
        },
        format="json",
    ).json()
    cand = a["candidates"][0]["id"]
    admin.post(
        f"{R}/assessments/{a['id']}/marks",
        {
            "version": a["version"],
            "marks": [
                {"candidate": cand, "component": scheme["components"][0]["id"], "status": "scored", "score": "41"}
            ],
        },
        format="json",
    )
    teacher = client_for(world.a.slug, factories.member(world.a, role="exam_officer"))
    for client, action in ((admin, "submit"), (teacher, "moderate"), (admin, "publish")):
        current = admin.get(f"{R}/assessments/{a['id']}").json()
        client.post(f"{R}/assessments/{a['id']}/{action}", {"version": current["version"]}, format="json")
    admin.post(
        f"{R}/students/{kiran.id}/promotion", {"year": str(school.year.id), "decision": "promote"}, format="json"
    )
    card = admin.post(
        f"{R}/students/{kiran.id}/documents", {"kind": "report_card", "term": str(term.id)}, format="json"
    )
    assert card.status_code == 201, card.json()
    content = card.json()["content"]
    assert content["subjects"] == [
        {
            "subject": "Science",
            "assessment": "Science term test",
            "total": "82.00",
            "grade": "A",
            "outcome": "passed",
            "revision": 1,
        }
    ]
    assert content["promotion"] == "Promoted" and content["attendance"]["counted"] == 0
    switch_on(world.a, modules=("admissions", "students", "academics", "attendance", "exams"))
    assert (
        admin.post(
            f"{R}/students/{kiran.id}/documents", {"kind": "report_card", "term": str(term.id)}, format="json"
        ).status_code
        == 404
    )
