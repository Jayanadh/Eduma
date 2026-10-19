"""A student record shows its own history (slice 4b S4B-11)."""

import datetime as dt

from accounts.permissions import today_for
from students import guardians
from students.models import Enrollment
from testing import factories

from .test_family import EVIDENCE


def test_history_lists_this_students_changes(world, enrolled, registrar):
    record = f"/api/v1/institution/students/{enrolled.id}"
    current = registrar.get(record).json()
    registrar.patch(record, {"version": current["version"], "full_name": "Meera R. Rao"}, format="json")
    link = enrolled.guardian_links.get()
    guardians.verify(world.a_admin, link, link.version, EVIDENCE)
    Enrollment.objects.filter(student=enrolled).update(entry_date=today_for(world.a) - dt.timedelta(days=30))
    current = registrar.get(record).json()
    body = {"version": current["version"], "effective_on": str(today_for(world.a)), "reason": "Family moved."}
    assert registrar.post(f"{record}/withdraw", body, format="json").status_code == 200
    history = registrar.get(f"{record}/history").json()
    assert history["count"] == 5
    rows = history["results"]
    assert rows[0]["action"] == "student.withdrawn" and rows[0]["actor"]
    assert {row["action"] for row in rows} == {
        "student.withdrawn",
        "student.guardian_verified",
        "student.updated",
        "student.guardian_proposed",
        "student.enrolled",
    }
    corrected = next(row for row in rows if row["action"] == "student.updated")
    assert corrected["changes"]["full_name"] == {"from": "Meera Rao", "to": "Meera R. Rao"}
    assert "No contact" not in str(history) and "Aadhaar" not in str(history)


def test_history_needs_scope(world, enrolled, client_for):
    city = factories.campus(world.a, code="CITY", name="City campus")
    reader = client_for(world.a.slug, factories.member(world.a, role="principal", scope=city))
    assert reader.get(f"/api/v1/institution/students/{enrolled.id}/history").status_code == 404
