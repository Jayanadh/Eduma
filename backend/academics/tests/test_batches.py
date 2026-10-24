"""College batches: sections of a program instead of a grade (slice 5b S5B-06; spec §7.5, Review Focus 3)."""

import pytest
from django.db import IntegrityError

from academics.models import EnrollmentPeriod, Program, Section
from testing import factories

from .conftest import API, enrolled_student, section_body
from .test_placement import place
from .test_teaching import CLASSES, teach


@pytest.fixture
def bsc(world, school):
    school.bsc = Program.objects.create(
        institution=world.a, code="BSC-PHY", name="B.Sc Physics", qualification="B.Sc", length_terms=6
    )
    school.bcom = Program.objects.create(
        institution=world.a, code="BCOM", name="B.Com", qualification="B.Com", length_terms=6
    )
    return school  # fmt: skip


def batch_body(school, **changes):
    return section_body(school, **{"grade": None, "program": str(school.bsc.id), "code": "BSC-PHY 2026 A", **changes})


def fields(response):
    return [e["field"] for e in response.json()["errors"]]


def test_a_batch_names_a_program(world, admin, bsc):
    made = admin.post(f"{API}/sections", batch_body(bsc), format="json")
    assert made.status_code == 201, made.json()
    assert made.json()["grade"] is None and made.json()["program"]["name"] == "B.Sc Physics"
    assert made.json()["level"] == "B.Sc Physics"
    both = admin.post(f"{API}/sections", batch_body(bsc, grade=str(bsc.c6.id), code="X"), format="json")
    assert fields(both) == ["grade"]
    neither = admin.post(f"{API}/sections", batch_body(bsc, program=None, code="Y"), format="json")
    assert fields(neither) == ["grade"]
    elsewhere = Program.objects.create(institution=world.b, code="P", name="P", qualification="Q", length_terms=2)
    assert fields(
        admin.post(f"{API}/sections", batch_body(bsc, program=str(elsewhere.id), code="Z"), format="json")
    ) == ["program"]
    assert admin.get(f"{API}/sections", {"program": str(bsc.bsc.id)}).json()["count"] == 1


def test_patch_keeps_exactly_one(admin, bsc):
    """Review Focus 3."""
    school_section = admin.post(f"{API}/sections", section_body(bsc), format="json").json()
    url = f"{API}/sections/{school_section['id']}"
    both = admin.patch(url, {"version": school_section["version"], "program": str(bsc.bsc.id)}, format="json")
    assert both.status_code == 422 and fields(both) == ["grade"]
    neither = admin.patch(url, {"version": school_section["version"], "grade": None}, format="json")
    assert neither.status_code == 422 and fields(neither) == ["grade"]
    section = Section.objects.get(pk=school_section["id"])
    assert (section.grade_id, section.program_id, section.version) == (bsc.c6.id, None, school_section["version"])
    swapped = admin.patch(
        url, {"version": school_section["version"], "grade": None, "program": str(bsc.bsc.id)}, format="json"
    )
    assert swapped.status_code == 200 and swapped.json()["level"] == "B.Sc Physics"


def test_placement_roster_and_label(world, admin, bsc, client_for):
    batch = Section.objects.get(pk=admin.post(f"{API}/sections", batch_body(bsc), format="json").json()["id"])
    student = enrolled_student(world.a, "2026-0001", name="Asha Rao")
    assert place(admin, batch, student).status_code == 201
    period = EnrollmentPeriod.objects.get(section=batch)
    assert (period.grade_id, period.program_id) == (None, bsc.bsc.id)
    assert [row["student"]["number"] for row in admin.get(f"{API}/sections/{batch.id}/students").json()] == [
        "2026-0001"
    ]
    record = admin.get(f"/api/v1/institution/students/{student.id}").json()
    assert record["current_section"] == "B.Sc Physics · BSC-PHY 2026 A"
    taken = admin.patch(
        f"{API}/sections/{batch.id}", {"version": batch.version, "program": str(bsc.bcom.id)}, format="json"
    )
    assert fields(taken) == ["program"]
    teacher = factories.member(world.a, role="teacher")
    teach(admin, batch, teacher)
    assert client_for(world.a.slug, teacher).get(CLASSES).json()[0]["section"]["grade"] == "B.Sc Physics"


def test_move_up_keeps_the_program(world, admin, bsc):
    batch = Section.objects.get(pk=admin.post(f"{API}/sections", batch_body(bsc), format="json").json()["id"])
    place(admin, batch, enrolled_student(world.a, "2026-0001"))
    following = admin.post(f"{API}/sections", batch_body(bsc, year=str(bsc.next_year.id)), format="json").json()
    other = admin.post(
        f"{API}/sections",
        batch_body(bsc, year=str(bsc.next_year.id), program=str(bsc.bcom.id), code="BCOM 2027 A"),
        format="json",
    ).json()
    grade = admin.post(
        f"{API}/sections", section_body(bsc, year=str(bsc.next_year.id), grade=str(bsc.c7.id), code="7A"), format="json"
    ).json()
    url = f"{API}/sections/{batch.id}/move-up"
    assert fields(admin.post(url, {"target": other["id"], "mode": "promote"}, format="json")) == ["target"]
    assert fields(admin.post(url, {"target": grade["id"], "mode": "promote"}, format="json")) == ["target"]
    assert fields(admin.post(url, {"target": following["id"], "mode": "repeat"}, format="json")) == ["mode"]
    preview = admin.post(f"{url}/preview", {"target": following["id"], "mode": "promote"}, format="json").json()
    ids = [row["student"]["id"] for row in preview]
    moved = admin.post(url, {"target": following["id"], "mode": "promote", "students": ids}, format="json")
    assert moved.json() == {"moved": 1}
    assert EnrollmentPeriod.objects.get(section_id=following["id"]).program_id == bsc.bsc.id


def test_a_placement_names_exactly_one(world, bsc):
    batch = Section.objects.create(
        institution=world.a, year=bsc.year, program=bsc.bsc, campus=bsc.main, code="B", capacity=5
    )
    student = enrolled_student(world.a, "2026-0009")
    with pytest.raises(IntegrityError):
        EnrollmentPeriod.objects.create(
            enrollment=student.enrollments.get(), institution=world.a, year=bsc.year, section=batch, campus=bsc.main
        )
