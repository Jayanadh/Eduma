import uuid

import pytest

from common.models import AuditEvent
from sites.models import SiteRevision

DRAFT = "/api/v1/institution/site/draft"


def platform_draft(institution) -> str:
    return f"/api/v1/platform/institutions/{institution.id}/site/draft"


def payload(draft: dict, **changes) -> dict:
    body = {
        "version": draft["version"],
        "primary_color": draft["theme"]["primary_color"],
        "secondary_color": draft["theme"]["secondary_color"],
        "heading_font": draft["theme"]["heading_font"],
        "body_font": draft["theme"]["body_font"],
        "logo": None,
        "content": draft["content"],
    }
    body.update(changes)
    return body


@pytest.fixture
def admin_a(world, client_for):
    return client_for(world.a.slug, world.a_admin)


def test_draft_created_from_defaults_then_published(world, admin_a):
    draft = admin_a.get(DRAFT).json()
    assert draft["status"] == "draft"
    assert draft["number"] == 1
    assert draft["theme"] == {
        "primary_color": "#4B5AE4",
        "secondary_color": "#FFD43B",
        "heading_font": "bricolage",
        "body_font": "dm-sans",
        "primary_fill": "#4B5AE4",
        "on_primary": "#FFFFFF",
        "primary_text": "#4B5AE4",
        "secondary_fill": "#FFD43B",
        "on_secondary": "#17132B",
        "secondary_text": draft["theme"]["secondary_text"],
    }
    assert draft["content"]["sections"][0]["title"] == "Welcome to Aster School"
    assert admin_a.get(DRAFT).json()["id"] == draft["id"]  # one draft, not a new one per visit
    published = admin_a.post(f"{DRAFT}/publish", {"version": draft["version"]}).json()
    assert published["status"] == "published"
    assert published["published_by_name"] == world.a_admin.full_name
    assert AuditEvent.objects.filter(action="site.published", institution=world.a).exists()


def test_publish_supersedes_previous_and_next_draft_copies_published(world, admin_a):
    first = admin_a.get(DRAFT).json()
    admin_a.post(f"{DRAFT}/publish", {"version": first["version"]})
    second = admin_a.get(DRAFT).json()
    assert second["number"] == 2
    assert second["content"] == first["content"]
    admin_a.put(DRAFT, payload(second, primary_color="#5B3FD9"))
    current = admin_a.get(DRAFT).json()
    admin_a.post(f"{DRAFT}/publish", {"version": current["version"]})
    statuses = dict(SiteRevision.objects.filter(institution=world.a).values_list("number", "status"))
    assert statuses == {1: "superseded", 2: "published"}


def test_save_validates_and_derives_theme(admin_a):
    draft = admin_a.get(DRAFT).json()
    saved = admin_a.put(DRAFT, payload(draft, primary_color="#ffd43b", heading_font="fredoka")).json()
    assert saved["theme"]["primary_color"] == "#FFD43B"
    assert saved["theme"]["on_primary"] == "#17132B"
    assert saved["version"] == draft["version"] + 1


def test_stale_save_is_409_with_current_version(admin_a):
    draft = admin_a.get(DRAFT).json()
    assert admin_a.put(DRAFT, payload(draft)).status_code == 200
    stale = admin_a.put(DRAFT, payload(draft))
    assert stale.status_code == 409
    assert stale.json()["code"] == "version_conflict"
    assert stale.json()["current_version"] == draft["version"] + 1


def test_stale_publish_is_409(admin_a):
    draft = admin_a.get(DRAFT).json()
    admin_a.put(DRAFT, payload(draft))
    assert admin_a.post(f"{DRAFT}/publish", {"version": draft["version"]}).status_code == 409


def test_saving_or_publishing_a_draft_someone_already_published_is_409(admin_a):
    draft = admin_a.get(DRAFT).json()
    admin_a.post(f"{DRAFT}/publish", {"version": draft["version"]})
    again = admin_a.post(f"{DRAFT}/publish", {"version": draft["version"]})
    assert again.status_code == 409 and again.json()["code"] == "version_conflict"
    assert admin_a.put(DRAFT, payload(draft)).json()["code"] == "version_conflict"


def test_restore_copies_old_revision_into_draft(world, admin_a):
    first = admin_a.get(DRAFT).json()
    admin_a.post(f"{DRAFT}/publish", {"version": first["version"]})
    second = admin_a.get(DRAFT).json()
    admin_a.put(DRAFT, payload(second, primary_color="#0F766E"))
    restored = admin_a.post(f"/api/v1/institution/site/revisions/{first['id']}/restore").json()
    assert restored["status"] == "draft"
    assert restored["id"] == second["id"]
    assert restored["theme"]["primary_color"] == "#4B5AE4"
    history = admin_a.get("/api/v1/institution/site/revisions").json()
    assert [item["number"] for item in history] == [2, 1]
    assert AuditEvent.objects.filter(action="site.restored").exists()


def test_platform_admin_edits_any_institution_via_platform_path(world, client_for):
    client = client_for(None, world.platform_admin)
    draft = client.get(platform_draft(world.b)).json()
    assert draft["content"]["sections"][0]["title"] == "Welcome to Birch College"
    assert client.put(platform_draft(world.b), payload(draft, body_font="lora")).status_code == 200
    missing = f"/api/v1/platform/institutions/{uuid.uuid4()}/site/draft"
    assert client.get(missing).status_code == 404


def test_wrong_host_is_404(world, client_for):
    assert client_for(world.a.slug, world.platform_admin).get(platform_draft(world.a)).status_code == 404
    assert client_for(None, world.a_admin).get(DRAFT).status_code == 404


def test_member_of_a_cannot_reach_b_draft_on_b_host(world, client_for):
    assert client_for(world.b.slug, world.a_admin).get(DRAFT).status_code == 403
    assert client_for(world.a.slug, world.a_admin).get(platform_draft(world.a)).status_code == 404


def test_revision_of_another_institution_is_not_found(world, client_for):
    other = client_for(world.b.slug, world.b_admin).get(DRAFT).json()
    response = client_for(world.a.slug, world.a_admin).post(f"/api/v1/institution/site/revisions/{other['id']}/restore")
    assert response.status_code == 404


def test_bad_theme_and_content_rejected(admin_a):
    draft = admin_a.get(DRAFT).json()
    response = admin_a.put(DRAFT, payload(draft, primary_color="#12345", heading_font="comic-sans"))
    assert response.status_code == 422
    assert {e["field"] for e in response.json()["errors"]} == {"primary_color", "heading_font"}
    bad_content = {
        "sections": [
            {"id": "hero", "type": "hero", "title": "x", "primary_cta": {"label": "Go", "href": "javascript:alert(1)"}}
        ]
    }
    response = admin_a.put(DRAFT, payload(draft, content=bad_content))
    assert response.json()["errors"][0]["field"] == "content.sections.0.primary_cta.href"


def test_unknown_logo_rejected(admin_a):
    draft = admin_a.get(DRAFT).json()
    response = admin_a.put(DRAFT, payload(draft, logo=str(uuid.uuid4())))
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "logo"
