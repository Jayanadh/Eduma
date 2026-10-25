"""Cutover rehearsal (BUILD-12): import the sample file, reconcile, retry the same file, reconcile again — the numbers
must not move, and every unresolved item is counted."""

from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from operations.reconcile import cutover_report

from .helpers import upload

SAMPLE = Path(__file__).resolve().parents[1] / "fixtures" / "aster-students-sample.csv"


@pytest.fixture
def admin(world, on, main, client_for):  # noqa: F811
    return client_for(world.a.slug, world.a_admin)


def send(admin):
    job = upload(admin, SimpleUploadedFile("sample.csv", SAMPLE.read_bytes(), content_type="text/csv")).json()
    return admin.post(f"/api/v1/institution/imports/{job['id']}/commit", {"version": job["version"]}, format="json")


def test_import_rehearsal_reconciles_and_a_retry_changes_nothing(world, admin):
    before = cutover_report(world.a)
    assert before["students"] == {} and before["unresolved"]["imports_not_committed"] == 0
    first = send(admin)
    assert first.status_code == 200, first.json()
    created = first.json()["totals"]["created"]
    after = cutover_report(world.a)
    assert created > 0
    assert after["students"] == {"active": created} and after["active_enrollments"] == created
    assert after["imported_records"]["student"] == created
    assert after["fees"]["trial_balance_net"] == "0.00"
    retry = send(admin)
    assert retry.json()["totals"]["created"] == 0  # the same file again creates nobody
    again = cutover_report(world.a)
    assert {k: v for k, v in again.items() if k != "unresolved"} == {
        k: v for k, v in after.items() if k != "unresolved"
    }
