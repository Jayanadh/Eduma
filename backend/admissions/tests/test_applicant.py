import datetime as dt

import pytest

from accounts.permissions import today_for
from admissions.models import Application, Submission

from .conftest import APPS, applicant, complete


def start(client, cycle, place=0, key=None):
    headers = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
    body = {"cycle": cycle["id"], "place": cycle["places"][place]["id"]}
    return client.post(APPS, body, format="json", **headers)


def attach_documents(application_id):
    """Stand-in uploads for this file's tests (the upload route itself is tested in test_documents)."""
    from django.core.files.base import ContentFile

    from admissions.models import Document

    row = Application.objects.get(pk=application_id)
    for requirement in row.cycle.documents.all():
        Document.objects.create(
            application=row,
            requirement=requirement,
            file=ContentFile(b"%PDF-1.4", name="x.pdf"),
            original_name="x.pdf",
            content_type="application/pdf",
            size=8,
            uploaded_by=row.owner,
        )


@pytest.fixture
def asha(world, cycle, client_for):
    return client_for(world.a.slug, applicant(world.a, "asha.parent"))


def submitted(client, cycle):
    draft = start(client, cycle).json()
    saved = client.patch(f"{APPS}/{draft['id']}", complete(draft), format="json").json()
    attach_documents(draft["id"])
    return client.post(f"{APPS}/{draft['id']}/submit", {"version": saved["version"]}, format="json")


def test_owner_isolation_and_ignored_fields(world, cycle, asha, client_for):
    """TST-033."""
    ravi = client_for(world.a.slug, applicant(world.a, "ravi.parent"))
    mine = start(asha, cycle).json()
    assert mine["stage"] == "draft" and mine["number"] == ""
    assert ravi.get(f"{APPS}/{mine['id']}").status_code == 404
    assert ravi.patch(f"{APPS}/{mine['id']}", complete(mine), format="json").status_code == 404
    assert ravi.get(APPS).json()["count"] == 0
    sneaky = {**complete(mine), "stage": "accepted", "owner": "x", "number": "A1", "institution": str(world.b.id)}
    saved = asha.patch(f"{APPS}/{mine['id']}", sneaky, format="json").json()
    assert (saved["stage"], saved["number"]) == ("draft", "")
    assert "notes" not in saved and "decided_by" not in saved
    assert asha.get("/api/v1/institution").status_code == 403
    assert asha.get("/api/v1/institution/admissions/cycles").status_code in (403, 404)


def test_start_is_idempotent(world, cycle, asha):
    first = start(asha, cycle, key="5d3d0f44-6bdb-4f21-9a35-2c5e22d1a0aa").json()
    again = start(asha, cycle, key="5d3d0f44-6bdb-4f21-9a35-2c5e22d1a0aa").json()
    assert first["id"] == again["id"] and Application.objects.count() == 1


def test_submit_lists_what_is_missing(world, cycle, asha):
    draft = start(asha, cycle).json()
    refused = asha.post(f"{APPS}/{draft['id']}/submit", {"version": draft["version"]}, format="json")
    assert refused.status_code == 422
    fields = {error["field"] for error in refused.json()["errors"]}
    assert {
        "learner_name",
        "date_of_birth",
        "answers.LANG",
        "answers.BUS",
        "documents.BIRTH",
        "documents.PHOTO",
    } <= fields
    assert "answers.STREAM" not in fields


def test_impossible_or_future_birth_dates(world, cycle, asha):
    """Review Focus 2."""
    draft = start(asha, cycle).json()
    future = str(today_for(world.a) + dt.timedelta(days=1))
    for bad in (future, "2027-02-31"):
        response = asha.patch(f"{APPS}/{draft['id']}", {**complete(draft), "date_of_birth": bad}, format="json")
        assert response.status_code == 422 and response.json()["errors"][0]["field"] == "date_of_birth", bad
    wrong = asha.patch(f"{APPS}/{draft['id']}", {**complete(draft), "answers": {"STREAM": "French"}}, format="json")
    assert wrong.json()["errors"][0]["field"] == "answers.STREAM"


def test_submit_numbers_snapshots_and_locks_editing(world, cycle, asha):
    response = submitted(asha, cycle)
    assert response.status_code == 200, response.json()
    body = response.json()
    year = cycle["entry_year"]
    assert (body["stage"], body["number"]) == ("submitted", f"A{year}-0001")
    snap = Submission.objects.get(application_id=body["id"])
    assert snap.revision == 1 and snap.snapshot["learner_name"] == "Meera Rao"
    assert snap.snapshot["documents"][0]["code"] in ("BIRTH", "PHOTO")
    edit = asha.patch(f"{APPS}/{body['id']}", complete(body), format="json")
    assert edit.status_code == 409 and edit.json()["code"] == "invalid_transition"


def test_double_submit_is_a_version_conflict(world, cycle, asha):
    """Review Focus 1."""
    draft = start(asha, cycle).json()
    saved = asha.patch(f"{APPS}/{draft['id']}", complete(draft), format="json").json()
    attach_documents(draft["id"])
    first = asha.post(f"{APPS}/{draft['id']}/submit", {"version": saved["version"]}, format="json")
    second = asha.post(f"{APPS}/{draft['id']}/submit", {"version": saved["version"]}, format="json")
    assert first.status_code == 200 and second.status_code == 409
    assert Submission.objects.count() == 1


def test_closed_cycles_refuse_new_applications_and_submissions(world, cycle, asha):
    draft = start(asha, cycle).json()
    from admissions.models import AdmissionCycle

    AdmissionCycle.objects.filter(pk=cycle["id"]).update(closes_on=today_for(world.a) - dt.timedelta(days=1))
    saved = asha.patch(f"{APPS}/{draft['id']}", complete(draft), format="json").json()
    attach_documents(draft["id"])
    late = asha.post(f"{APPS}/{draft['id']}/submit", {"version": saved["version"]}, format="json")
    assert late.status_code == 409 and late.json()["code"] == "admissions_closed"
    assert start(asha, cycle).status_code == 409


def test_withdraw_and_accept_rules(world, cycle, asha):
    body = submitted(asha, cycle).json()
    row = Application.objects.get(pk=body["id"])
    row.stage = "offered"
    row.offer_expires_on = today_for(world.a) + dt.timedelta(days=7)
    row.save()
    accepted = asha.post(f"{APPS}/{body['id']}/accept", {"version": row.version}, format="json")
    assert accepted.status_code == 200 and accepted.json()["stage"] == "accepted"
    late = asha.post(f"{APPS}/{body['id']}/withdraw", {"version": accepted.json()["version"]}, format="json")
    assert late.status_code == 409


def test_expired_offers_cannot_be_accepted(world, cycle, asha):
    body = submitted(asha, cycle).json()
    row = Application.objects.get(pk=body["id"])
    row.stage = "offered"
    row.offer_expires_on = today_for(world.a) - dt.timedelta(days=1)
    row.save()
    refused = asha.post(f"{APPS}/{body['id']}/accept", {"version": row.version}, format="json")
    assert refused.status_code == 409
    assert asha.get(f"{APPS}/{body['id']}").json()["stage"] == "offer_expired"
