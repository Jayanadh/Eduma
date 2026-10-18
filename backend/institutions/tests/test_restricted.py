import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.tests.test_auth import host, login
from common.models import AuditEvent
from testing import factories
from testing.factories import PASSWORD

from .test_lifecycle import URL, post_transition


@pytest.fixture
def platform(world, client_for):
    return client_for(None, world.platform_admin)


@pytest.fixture
def restricted(world, platform):
    assert post_transition(platform, world.a, "restricted", reason="Fees overdue").status_code == 200
    world.a.refresh_from_db()
    return world.a


def test_restrict_and_lift_are_audited_moves(world, platform, restricted):
    assert restricted.lifecycle_status == "restricted"
    assert AuditEvent.objects.filter(action="institution.restricted", institution=world.a).exists()
    lifted = post_transition(platform, world.a, "active", reason="Paid")
    assert lifted.status_code == 200 and lifted.json()["lifecycle_status"] == "active"
    assert AuditEvent.objects.filter(action="institution.restriction_lifted").exists()
    fresh = factories.institution(lifecycle_status="setup")
    assert post_transition(platform, fresh, "restricted").status_code == 409


def test_restricted_can_be_suspended_or_archived(world, platform, restricted):
    assert post_transition(platform, world.a, "suspended").status_code == 200
    other = factories.institution()
    post_transition(platform, other, "restricted")
    assert post_transition(platform, other, "archived").status_code == 200


def test_members_read_but_cannot_write(world, restricted, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    assert admin.get("/api/v1/institution/campuses").status_code == 200
    refused = admin.post("/api/v1/institution/campuses", {"code": "CITY", "name": "City"})
    assert refused.status_code == 403
    assert refused.json()["code"] == "institution_restricted"
    assert refused.json()["detail"] == "Aster School is read-only for now: Fees overdue"
    assert admin.put("/api/v1/institution/site/draft", {}, format="json").status_code == 403
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20)).save(buffer, format="PNG")
    upload = SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")
    assert admin.post("/api/v1/institution/site/assets", {"file": upload}, format="multipart").status_code == 403


def test_session_still_works_while_restricted(world, restricted):
    client = host(world.a.slug)
    assert login(client, world.a_admin.username).status_code == 200
    me = client.get("/api/v1/session").json()["user"]["membership"]
    assert me["restricted"] is True and me["status_reason"] == "Fees overdue"
    changed = client.post(
        "/api/v1/session/change-password", {"old_password": PASSWORD, "new_password": "Another-pass-2026"}
    )
    assert changed.status_code in (200, 204)
    assert client.post("/api/v1/session/logout").status_code in (200, 204)


def test_public_page_stays_up(world, restricted, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    restricted.lifecycle_status = "active"
    restricted.save()
    draft = admin.get("/api/v1/institution/site/draft").json()
    admin.post("/api/v1/institution/site/draft/publish", {"version": draft["version"]})
    restricted.lifecycle_status = "restricted"
    restricted.save()
    assert client_for(world.a.slug).get("/api/v1/public/site").json()["mode"] == "full"


def test_platform_host_is_unaffected(world, platform, restricted):
    detail = platform.get(f"{URL}/{world.a.id}").json()
    saved = platform.patch(f"{URL}/{world.a.id}", {"version": detail["version"], "contact_phone": "+91 1"})
    assert saved.status_code == 200


def test_lifting_the_restriction_restores_writes(world, platform, restricted, client_for):
    """Spec §9.7: after the platform lifts it, members can change things again."""
    admin = client_for(world.a.slug, world.a_admin)
    assert admin.post("/api/v1/institution/campuses", {"code": "CITY", "name": "City"}).status_code == 403
    assert post_transition(platform, world.a, "active", reason="Paid").status_code == 200
    assert admin.post("/api/v1/institution/campuses", {"code": "CITY", "name": "City"}).status_code == 201


def test_members_see_the_platform_note_only_while_restricted(world, platform, client_for):
    """Final review #7: an activation or override note is the platform's own; a restriction reason is for members."""
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    world.a.status_reason = "Activated early: board letter pending"
    world.a.save()
    assert teacher.get("/api/v1/institution").json()["status_reason"] == ""
    post_transition(platform, world.a, "restricted", reason="Fees overdue")
    assert teacher.get("/api/v1/institution").json()["status_reason"] == "Fees overdue"


def test_lifting_reads_well_in_the_audit_log(world, platform, restricted):
    """Final review #11."""
    post_transition(platform, world.a, "active", reason="Paid")
    lifted = AuditEvent.objects.get(action="institution.restriction_lifted")
    assert lifted.summary == "Lifted the restriction on Aster School"
    assert AuditEvent.objects.get(action="institution.restricted").summary == "Restricted Aster School"
