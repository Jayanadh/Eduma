import pytest
from django.utils import timezone

from accounts.models import Membership
from common.models import AuditEvent
from sites.models import SiteRevision
from testing import factories

URL = "/api/v1/platform/institutions"


@pytest.fixture
def platform(world, client_for):
    return client_for(None, world.platform_admin)


def post_transition(client, institution, to, reason="Because", override_reason="", version=None):
    institution.refresh_from_db()
    body = {
        "to": to,
        "reason": reason,
        "override_reason": override_reason,
        "version": institution.version if version is None else version,
    }
    return client.post(f"{URL}/{institution.id}/transition", body)


def make_ready(institution, admin):
    admin.last_login = timezone.now()
    admin.save()
    SiteRevision.objects.create(
        institution=institution,
        number=1,
        status="published",
        primary_color="#4B5AE4",
        secondary_color="#FFD43B",
        heading_font="bricolage",
        body_font="dm-sans",
        content={"sections": []},
    )


@pytest.mark.parametrize(
    "start,to,ok",
    [
        ("setup", "active", True),
        ("active", "suspended", True),
        ("suspended", "active", True),
        ("setup", "archived", True),
        ("active", "archived", True),
        ("suspended", "archived", True),
        ("archived", "active", False),
        ("setup", "suspended", False),
        ("active", "active", False),
        ("active", "setup", False),
        ("archived", "archived", False),
    ],
)
def test_transition_table(world, platform, start, to, ok):
    make_ready(world.a, world.a_admin)
    world.a.lifecycle_status = start
    world.a.save()
    response = post_transition(platform, world.a, to)
    if ok:
        assert response.status_code == 200, response.json()
        assert response.json()["lifecycle_status"] == to
        assert response.json()["status_reason"] == "Because"
    else:
        assert response.status_code == 409
        assert response.json()["code"] == "invalid_transition"


def test_unknown_target_state_is_422(world, platform):
    assert post_transition(platform, world.a, "deleted").status_code == 422


def test_activation_needs_readiness_or_override(platform):
    institution = factories.institution(lifecycle_status="setup")
    factories.member(institution)
    response = post_transition(platform, institution, "active", reason="Go live")
    assert response.status_code == 422
    error = response.json()["errors"][0]
    assert error["field"] == "override_reason"
    assert error["message"] == (
        "Readiness checks are not complete: Institution Admin has signed in and changed their first password, "
        "Public page is published. Give an override reason to activate anyway."
    )
    response = post_transition(platform, institution, "active", reason="Go live", override_reason="Pilot demo")
    assert response.json()["lifecycle_status"] == "active"
    assert response.json()["activated_at"] is not None
    event = AuditEvent.objects.get(action="institution.activated")
    assert event.changes == {"from": "setup", "to": "active", "reason": "Go live", "override_reason": "Pilot demo"}


def test_ready_institution_activates_without_override(world, platform):
    make_ready(world.a, world.a_admin)
    world.a.lifecycle_status = "setup"
    world.a.save()
    assert post_transition(platform, world.a, "active").status_code == 200


def test_reason_required(world, platform):
    response = post_transition(platform, world.a, "suspended", reason="  ")
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "reason"


def test_stale_version_is_409(world, platform):
    response = post_transition(platform, world.a, "suspended", version=world.a.version - 1 or 99)
    assert response.json()["code"] == "version_conflict"


def test_reactivation_needs_an_active_admin(world, platform):
    world.a.lifecycle_status = "suspended"
    world.a.save()
    Membership.objects.filter(institution=world.a).update(status="revoked")
    response = post_transition(platform, world.a, "active")
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"


def test_actions_are_audited_by_name(world, platform):
    post_transition(platform, world.a, "suspended")
    post_transition(platform, world.a, "active")
    post_transition(platform, world.a, "archived")
    actions = list(AuditEvent.objects.filter(institution=world.a).order_by("at").values_list("action", flat=True))
    assert actions == ["institution.suspended", "institution.reactivated", "institution.archived"]


def test_overview_counts_and_needs_action(world, platform):
    older = factories.institution(lifecycle_status="setup", display_name="Older")
    newer = factories.institution(lifecycle_status="setup", display_name="Newer", contact_phone="")
    factories.institution(lifecycle_status="suspended")
    body = platform.get("/api/v1/platform/overview").json()
    assert body["counts"] == {"setup": 2, "active": 2, "suspended": 1, "archived": 0, "restricted": 0}
    assert [item["display_name"] for item in body["needs_action"]] == ["Older", "Newer"]
    assert body["needs_action"][0]["id"] == str(older.id)
    assert body["needs_action"][1]["missing"] == [
        "Institution Admin has signed in and changed their first password",
        "Public page is published",
        "Contact email and phone are filled in",
    ]
    assert newer.slug == body["needs_action"][1]["slug"]
