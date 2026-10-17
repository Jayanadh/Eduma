import pytest
from rest_framework.test import APIClient

from accounts.models import Membership
from common.models import AuditEvent
from testing.factories import PASSWORD

REFUSED = "Invalid login ID or password."


def host(slug: str | None, **kw) -> APIClient:
    """A client on the platform host (None) or an institution's host, using real sessions."""
    client = APIClient(HTTP_HOST="eduma.test" if slug is None else f"{slug}.eduma.test", **kw)
    client.get("/api/v1/session")
    return client


def login(client: APIClient, username: str, password: str = PASSWORD):
    return client.post("/api/v1/session/login", {"username": username, "password": password})


def me(client: APIClient):
    return client.get("/api/v1/session").json()["user"]


def test_platform_admin_signs_in_only_on_platform_host(world):
    client = host(None)
    response = login(client, world.platform_admin.username)
    assert response.status_code == 200
    assert response.json()["user"]["is_platform_admin"] is True
    assert me(client)["membership"] is None
    refused = login(host(world.a.slug), world.platform_admin.username)
    assert refused.status_code == 400
    assert refused.json()["detail"] == REFUSED


def test_member_signs_in_only_on_own_institution_host(world):
    client = host(world.a.slug)
    response = login(client, "ASTER.admin")
    assert response.status_code == 200
    membership = response.json()["user"]["membership"]
    assert membership["role"] == "INSTITUTION_ADMIN"
    assert "institution_brand.update" in membership["permissions"]
    assert login(host(world.b.slug), world.a_admin.username).json()["detail"] == REFUSED
    assert login(host(None), world.a_admin.username).json()["detail"] == REFUSED


def test_wrong_password_gets_the_same_refusal(world):
    assert login(host(world.a.slug), world.a_admin.username, "nope").json()["detail"] == REFUSED


def test_no_sign_in_on_unknown_host(world):
    assert login(host("nosuch"), world.a_admin.username).json()["detail"] == REFUSED


@pytest.mark.parametrize("state,allowed", [("setup", True), ("active", True), ("suspended", False), ("archived", False)])
def test_sign_in_depends_on_institution_state(world, state, allowed):
    world.a.lifecycle_status = state
    world.a.save()
    response = login(host(world.a.slug), world.a_admin.username)
    assert (response.status_code == 200) is allowed
    if not allowed:
        assert response.json()["detail"] == REFUSED


def test_switched_off_login_is_explained_only_with_the_right_password(world):
    world.a_admin.is_active = False
    world.a_admin.save()
    assert "switched off" in login(host(world.a.slug), world.a_admin.username).json()["detail"]
    assert login(host(world.a.slug), world.a_admin.username, "wrong").json()["detail"] == REFUSED
    # Not explained on a host where the login would not be allowed anyway.
    assert login(host(world.b.slug), world.a_admin.username).json()["detail"] == REFUSED


def test_session_reused_on_another_host_is_signed_out(world):
    client = host(world.a.slug)
    login(client, world.a_admin.username)
    assert me(client) is not None
    client.defaults["HTTP_HOST"] = f"{world.b.slug}.eduma.test"
    assert me(client) is None
    client.defaults["HTTP_HOST"] = f"{world.a.slug}.eduma.test"
    assert me(client) is None  # the session was ended, not just hidden


def test_suspension_signs_out_existing_session(world):
    client = host(world.a.slug)
    login(client, world.a_admin.username)
    world.a.lifecycle_status = "suspended"
    world.a.save()
    assert me(client) is None


def test_revoked_membership_signs_out(world):
    client = host(world.a.slug)
    login(client, world.a_admin.username)
    Membership.objects.filter(user=world.a_admin).update(status="revoked")
    assert me(client) is None


def test_platform_admin_who_loses_the_flag_is_signed_out(world):
    client = host(None)
    login(client, world.platform_admin.username)
    world.platform_admin.is_platform_admin = False
    world.platform_admin.save()
    assert me(client) is None


def test_first_password_must_be_changed(world):
    world.a_admin.must_change_password = True
    world.a_admin.save()
    client = host(world.a.slug)
    login(client, world.a_admin.username)
    blocked = client.get("/api/v1/institution")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "password_change_required"
    weak = client.post("/api/v1/session/change-password", {"old_password": PASSWORD, "new_password": "123"})
    assert weak.status_code == 422
    changed = client.post(
        "/api/v1/session/change-password", {"old_password": PASSWORD, "new_password": "Brand-new-pass-77"}
    )
    assert changed.status_code == 204
    assert me(client)["must_change_password"] is False
    assert client.get("/api/v1/institution").status_code != 403  # no longer blocked (route arrives in Task 7)


def test_logout_ends_the_session(world):
    client = host(world.a.slug)
    login(client, world.a_admin.username)
    assert client.post("/api/v1/session/logout").status_code == 204
    assert me(client) is None


def test_login_requires_csrf(world):
    client = host(world.a.slug, enforce_csrf_checks=True)
    response = login(client, world.a_admin.username)
    assert response.status_code == 403
    token = client.cookies["XSRF-TOKEN"].value
    ok = client.post(
        "/api/v1/session/login",
        {"username": world.a_admin.username, "password": PASSWORD},
        HTTP_X_XSRF_TOKEN=token,
    )
    assert ok.status_code == 200


def test_login_is_audited(world):
    login(host(world.a.slug), world.a_admin.username)
    event = AuditEvent.objects.get(action="auth.login")
    assert event.actor_id == world.a_admin.id
    assert event.institution_id == world.a.id


def test_login_is_throttled(world):
    client = host(world.a.slug)
    for _ in range(10):
        login(client, world.a_admin.username, "wrong")
    assert login(client, world.a_admin.username).json()["code"] == "rate_limited"
