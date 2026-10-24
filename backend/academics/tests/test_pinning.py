"""Pinning students to a program and regulation (slice 5b S5B-07; spec §7.6, Review Focus 4)."""

import pytest

from academics import curricula
from academics.models import CurriculumVersion, Program
from admissions.models import Place
from admissions.tests.conftest import CYCLES, cycle, cycle_body, main  # noqa: F401 — fixtures
from admissions.tests.test_enrollment import FIRST, accepted, registrar  # noqa: F401 — fixtures
from admissions.tests.test_review import act
from common.models import AuditEvent
from students.models import Student
from testing import factories

STUDENTS = "/api/v1/institution/students"


def regulation(program, code, cohort, revision=1, status="published"):
    return CurriculumVersion.objects.create(
        program=program, regulation=code, revision=revision, cohort=cohort, credits_required=120, status=status
    )


@pytest.fixture
def bsc(world, on):
    return Program.objects.create(
        institution=world.a, code="BSC-PHY", name="B.Sc Physics", qualification="B.Sc", length_terms=6
    )


def enrolled(world, cycle, accepted, registrar, program):  # noqa: F811
    Place.objects.filter(cycle_id=cycle["id"]).update(program=program)
    assert act(registrar, accepted, "enroll", password=FIRST).status_code == 200
    return Student.objects.get()


def test_for_cohort_picks_the_latest_published_for_the_entry_year(bsc):
    regulation(bsc, "R2026", 2026)
    second = regulation(bsc, "R2026", 2026, revision=2)
    regulation(bsc, "R2027", 2027, status="draft")
    regulation(bsc, "R2028", 2028)
    assert curricula.for_cohort(bsc, 2027) == second
    assert curricula.for_cohort(bsc, 2025) is None


def test_enrolling_pins_program_and_regulation(world, bsc, cycle, accepted, registrar):  # noqa: F811
    regulation(bsc, "R2026", 2026)
    second = regulation(bsc, "R2026", 2026, revision=2)
    regulation(bsc, "R2028", 2028)
    student = enrolled(world, cycle, accepted, registrar, bsc)
    enrollment = student.enrollments.get()
    assert (enrollment.program, enrollment.curriculum) == (bsc, second)
    record = registrar.get(f"{STUDENTS}/{student.id}").json()
    assert record["enrollment"]["program"]["code"] == "BSC-PHY"
    assert record["enrollment"]["curriculum"]["label"] == "R2026 rev 2"


def test_only_a_retired_regulation_pins_the_program_alone(world, bsc, cycle, accepted, registrar):  # noqa: F811
    """Review Focus 4."""
    regulation(bsc, "R2026", 2026, status="retired")
    enrollment = enrolled(world, cycle, accepted, registrar, bsc).enrollments.get()
    assert (enrollment.program, enrollment.curriculum) == (bsc, None)


def test_changing_the_pin(world, bsc, cycle, accepted, registrar, client_for):  # noqa: F811
    student = enrolled(world, cycle, accepted, registrar, bsc)
    r2026 = regulation(bsc, "R2026", 2026)
    retired = regulation(bsc, "R2024", 2024, status="retired")
    bcom = Program.objects.create(institution=world.a, code="BCOM", name="B.Com", qualification="B.Com", length_terms=6)
    theirs = regulation(bcom, "R2026", 2026)
    url = f"{STUDENTS}/{student.id}/program"

    def pin(client, curriculum, program=bsc, version=None):
        body = {"version": version or Student.objects.get().version, "program": str(program.id),
                "curriculum": str(curriculum.id) if curriculum else None}  # fmt: skip
        return client.post(url, body, format="json")

    assert [e["field"] for e in pin(registrar, theirs).json()["errors"]] == ["curriculum"]
    assert [e["field"] for e in pin(registrar, retired).json()["errors"]] == ["curriculum"]
    assert pin(registrar, r2026, version=99).status_code == 409
    reader = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert pin(reader, r2026).status_code in (403, 404)
    changed = pin(registrar, r2026)
    assert changed.status_code == 200, changed.json()
    assert changed.json()["enrollment"]["curriculum"]["label"] == "R2026 rev 1"
    event = AuditEvent.objects.filter(action="student.program_changed").get()
    assert event.changes["curriculum"] == {"from": None, "to": "BSC-PHY R2026 rev 1"}
    moved = pin(registrar, theirs, program=bcom)
    assert moved.status_code == 200 and moved.json()["enrollment"]["program"]["code"] == "BCOM"


def test_cycle_places_accept_a_program(world, bsc, main, client_for):  # noqa: F811
    admin = client_for(world.a.slug, world.a_admin)
    places = [{"code": "BSC", "label": "B.Sc Physics", "campus": str(main.id), "seats": 60, "program": str(bsc.id)}]
    made = admin.post(CYCLES, cycle_body(main, places=places), format="json")
    assert made.status_code == 201, made.json()
    assert made.json()["places"][0]["program"] == {"id": str(bsc.id), "code": "BSC-PHY", "name": "B.Sc Physics"}
    elsewhere = Program.objects.create(institution=world.b, code="X", name="X", qualification="X", length_terms=2)
    places[0]["program"] = str(elsewhere.id)
    assert admin.post(CYCLES, cycle_body(main, places=places), format="json").status_code == 422
