import copy
import uuid

import pytest

from accounts.models import Membership, User
from accounts.permissions import has_perm
from common.models import AuditEvent
from institutions.models import Institution
from sites.models import SiteRevision
from testing import factories

URL = "/api/v1/platform/institutions"
PAYLOAD = {
    "legal_name": "Aster School Trust",
    "display_name": "Aster School",
    "category": "school",
    "slug": "aster-school",
    "contact_email": "office@aster.example",
    "contact_phone": "+91 90000 00000",
    "address": "1 Lake Road",
    "admin": {"full_name": "Asha Rao", "username": "aster-school.admin", "password": "First-pass-2026"},
}


@pytest.fixture
def platform(world, client_for):
    return client_for(None, world.platform_admin)


def create(client, body=None, key=None):
    return client.post(URL, body or PAYLOAD, format="json", HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def counts():
    return Institution.objects.count(), User.objects.count(), Membership.objects.count(), SiteRevision.objects.count()


def test_create_is_atomic_and_complete(world, platform):
    response = create(platform)
    assert response.status_code == 201
    body = response.json()
    institution = Institution.objects.get(slug="aster-school")
    assert body["id"] == str(institution.id)
    assert institution.lifecycle_status == "setup"
    assert institution.created_by == world.platform_admin
    assert body["url"] == "http://aster-school.eduma.test"
    admin = User.objects.get(username="aster-school.admin")
    assert admin.must_change_password
    assert admin.check_password("First-pass-2026")
    assert has_perm(admin, institution, "institution_brand.update")
    draft = SiteRevision.objects.get(institution=institution)
    assert draft.status == "draft"
    assert draft.content["sections"][0]["title"] == "Welcome to Aster School"
    assert body["admin"]["username"] == "aster-school.admin"
    assert [item["done"] for item in body["readiness"]] == [False, False, True]
    assert AuditEvent.objects.filter(action="institution.created", institution=institution).exists()
    assert list(institution.campuses.values_list("code", "name")) == [("MAIN", "Main campus")]


def test_retry_with_same_key_returns_same_institution(platform):
    key = str(uuid.uuid4())
    first = create(platform, key=key)
    before = counts()
    again = create(platform, key=key)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]
    assert counts() == before


def test_same_key_different_body_is_409(platform):
    key = str(uuid.uuid4())
    create(platform, key=key)
    changed = {**PAYLOAD, "display_name": "Another School"}
    response = create(platform, changed, key=key)
    assert response.status_code == 409
    assert response.json()["code"] == "idempotency_mismatch"


def test_taken_slug_or_username_writes_nothing(world, platform):
    before = counts()
    taken_slug = create(platform, {**PAYLOAD, "slug": world.a.slug})
    assert taken_slug.status_code == 422
    assert taken_slug.json()["errors"][0]["field"] == "slug"
    taken_user = copy.deepcopy(PAYLOAD)
    taken_user["admin"]["username"] = world.a_admin.username
    response = create(platform, taken_user)
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "admin.username"
    assert counts() == before


def test_weak_first_password_and_reserved_slug_rejected(platform):
    weak = copy.deepcopy(PAYLOAD)
    weak["admin"]["password"] = "12345678"
    assert create(platform, weak).json()["errors"][0]["field"] == "admin.password"
    assert create(platform, {**PAYLOAD, "slug": "WWW"}).json()["errors"][0]["field"] == "slug"


def test_missing_or_bad_idempotency_key_is_400(platform):
    assert platform.post(URL, PAYLOAD, format="json").json()["code"] == "invalid_request"
    assert create(platform, key="not-a-uuid").json()["code"] == "invalid_request"


def test_list_search_needs_three_chars_and_filters(world, platform):
    factories.institution(
        slug="vector",
        display_name="Vector Engineering College",
        lifecycle_status="setup",
        category="engineering_college",
    )
    everyone = platform.get(URL).json()
    assert everyone["count"] == 3
    assert platform.get(URL, {"search": "as"}).json()["count"] == 3  # too short: ignored
    found = platform.get(URL, {"search": "ast"}).json()["results"]
    assert [item["slug"] for item in found] == ["aster"]
    assert platform.get(URL, {"search": "VECTOR"}).json()["count"] == 1
    assert [i["slug"] for i in platform.get(URL, {"status": "setup"}).json()["results"]] == ["vector"]
    assert [i["slug"] for i in platform.get(URL, {"category": "college"}).json()["results"]] == ["birch"]
    item = found[0]
    assert set(item) == {"id", "display_name", "slug", "url", "category", "lifecycle_status", "created_at", "ready"}
    assert item["ready"] is False


def test_slug_check(world, platform):
    check = platform.get(f"{URL}/slug-check", {"slug": world.a.slug}).json()
    assert check == {"available": False, "reason": "This address is already taken."}
    assert platform.get(f"{URL}/slug-check", {"slug": "www"}).json() == {
        "available": False,
        "reason": "This address is reserved.",
    }
    assert platform.get(f"{URL}/slug-check", {"slug": "New-Place"}).json() == {"available": True, "reason": ""}


def test_platform_edits_profile_with_version(world, platform):
    detail = platform.get(f"{URL}/{world.a.id}").json()
    response = platform.patch(
        f"{URL}/{world.a.id}", {"version": detail["version"], "display_name": "Aster Public School"}
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Aster Public School"
    stale = platform.patch(f"{URL}/{world.a.id}", {"version": detail["version"], "display_name": "Old"})
    assert stale.status_code == 409
    event = AuditEvent.objects.get(action="institution.updated")
    assert event.changes == {"display_name": {"from": "Aster School", "to": "Aster Public School"}}


def test_slug_locked_after_setup(world, platform):
    detail = platform.get(f"{URL}/{world.a.id}").json()
    response = platform.patch(f"{URL}/{world.a.id}", {"version": detail["version"], "slug": "aster-new"})
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"
    created = create(platform).json()
    renamed = platform.patch(f"{URL}/{created['id']}", {"version": created["version"], "slug": "aster-renamed"})
    assert renamed.json()["url"] == "http://aster-renamed.eduma.test"


def test_custom_domain_is_cleaned_checked_and_shown_as_the_url(world, platform):
    def patch(domain):
        detail = platform.get(f"{URL}/{world.a.id}").json()
        return platform.patch(f"{URL}/{world.a.id}", {"version": detail["version"], "custom_domain": domain})

    saved = patch(" https://WWW.Aster.edu.in/admissions ").json()
    assert saved["custom_domain"] == "www.aster.edu.in"
    assert saved["url"] == "http://www.aster.edu.in"
    for bad in ("not a domain", "localhost", "birch.eduma.test", "eduma.test"):
        assert patch(bad).status_code == 422, bad
    other = platform.get(f"{URL}/{world.b.id}").json()
    clash = platform.patch(f"{URL}/{world.b.id}", {"version": other["version"], "custom_domain": "www.aster.edu.in"})
    assert clash.json()["errors"][0]["field"] == "custom_domain"
    assert patch("").json()["url"] == "http://aster.eduma.test"


def test_reset_admin_password_forces_change(world, platform):
    response = platform.post(f"{URL}/{world.a.id}/admin-password", {"password": "Reset-pass-2026"})
    assert response.status_code == 204
    world.a_admin.refresh_from_db()
    assert world.a_admin.must_change_password
    assert world.a_admin.check_password("Reset-pass-2026")
    assert AuditEvent.objects.filter(action="membership.password_reset", institution=world.a).exists()
    assert platform.post(f"{URL}/{world.a.id}/admin-password", {"password": "123"}).status_code == 422


def test_reset_without_an_admin_is_409(platform):
    lonely = factories.institution()
    response = platform.post(f"{URL}/{lonely.id}/admin-password", {"password": "Reset-pass-2026"})
    assert response.status_code == 409


def test_institution_admin_reads_and_edits_own_profile(world, client_for):
    client = client_for(world.a.slug, world.a_admin)
    own = client.get("/api/v1/institution").json()
    assert own["display_name"] == "Aster School"
    assert own["url"] == "http://aster.eduma.test"
    assert "admin" not in own and "readiness" in own
    response = client.patch(
        "/api/v1/institution", {"version": own["version"], "address": "2 Hill Road", "display_name": "Ignored"}
    )
    assert response.status_code == 200
    world.a.refresh_from_db()
    assert world.a.address == "2 Hill Road"
    assert world.a.display_name == "Aster School"  # not theirs to change


def test_platform_routes_refuse_institution_admin(world, client_for):
    assert client_for(None, world.a_admin).get(URL).status_code == 403
    assert client_for(world.a.slug, world.a_admin).get(URL).status_code == 404
    assert client_for(None, world.platform_admin).get("/api/v1/institution").status_code == 404


def test_duplicate_udise_or_aishe_is_422_not_500(world, platform):
    world.a.udise_code = "28123456789"
    world.a.save()
    response = create(platform, {**PAYLOAD, "udise_code": "28123456789"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "udise_code"
