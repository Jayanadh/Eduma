import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

SITE = "/api/v1/public/site"


def publish(client) -> dict:
    draft = client.get("/api/v1/institution/site/draft").json()
    return client.post("/api/v1/institution/site/draft/publish", {"version": draft["version"]}).json()


def save(client, **changes) -> dict:
    draft = client.get("/api/v1/institution/site/draft").json()
    body = {"version": draft["version"], "logo": draft["logo"] and draft["logo"]["id"], "content": draft["content"],
            **{k: draft["theme"][k] for k in ("primary_color", "secondary_color", "heading_font", "body_font")}}
    body.update(changes)
    response = client.put("/api/v1/institution/site/draft", body)
    assert response.status_code == 200, response.json()
    return response.json()


def png() -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 20, 30)).save(buffer, format="PNG")
    return SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")


@pytest.fixture
def admin_a(world, client_for):
    return client_for(world.a.slug, world.a_admin)


def test_public_site_platform(world, client_for, settings):
    settings.EDUMA_CONTACT_EMAIL = "team@eduma.example"
    body = client_for(None).get(SITE).json()
    assert body["kind"] == "platform"
    assert body["content"]["sections"][0]["type"] == "hero"
    assert body["content"]["sections"][0]["primary_cta"]["href"] == "mailto:team@eduma.example"
    assert body["theme"]["primary_color"] == "#4B5AE4" and body["theme"]["on_primary"] == "#FFFFFF"
    assert body["logo_url"] == "/eduma-logo.png"


def test_active_site_shows_published_not_draft(world, admin_a, client_for):
    publish(admin_a)
    draft = save(admin_a, primary_color="#0F766E")
    draft["content"]["sections"][0]["title"] = "Draft title"
    save(admin_a, content=draft["content"])
    body = client_for(world.a.slug).get(SITE).json()
    assert body["kind"] == "institution" and body["mode"] == "full"
    assert body["content"]["sections"][0]["title"] == "Welcome to Aster School"
    assert body["theme"]["primary_color"] == "#4B5AE4"
    assert body["institution"] == {
        "slug": "aster", "display_name": "Aster School", "category": "school",
        "contact_email": world.a.contact_email, "contact_phone": world.a.contact_phone, "address": "",
    }


def test_image_urls_are_added_to_content(world, admin_a, client_for):
    asset = admin_a.post("/api/v1/institution/site/assets", {"file": png()}, format="multipart").json()["id"]
    draft = admin_a.get("/api/v1/institution/site/draft").json()
    draft["content"]["sections"][0]["images"][0]["asset"] = asset
    save(admin_a, logo=asset, content=draft["content"])
    publish(admin_a)
    body = client_for(world.a.slug).get(SITE).json()
    first = body["content"]["sections"][0]["images"][0]
    assert first == {"asset": asset, "alt": "Students in class", "url": f"/api/v1/public/assets/{asset}"}
    assert body["content"]["sections"][0]["images"][1]["url"] is None
    assert body["logo_url"] == f"/api/v1/public/assets/{asset}"


@pytest.mark.parametrize("state,mode", [("active", "full"), ("setup", "opening_soon"), ("suspended", "unavailable")])
def test_public_site_modes(world, admin_a, client_for, state, mode):
    publish(admin_a)
    world.a.lifecycle_status = state
    world.a.save()
    body = client_for(world.a.slug).get(SITE).json()
    assert body["mode"] == mode
    if mode == "unavailable":
        assert body == {"kind": "institution", "mode": "unavailable", "institution": {"display_name": "Aster School"}}
    if mode == "opening_soon":
        assert [s["type"] for s in body["content"]["sections"]] == ["hero"]
        assert body["content"]["sections"][0]["title"] == "Welcome to Aster School"


def test_setup_without_a_published_page_uses_the_draft_look(world, admin_a, client_for):
    world.a.lifecycle_status = "setup"
    world.a.save()
    save(admin_a, primary_color="#5B3FD9")
    body = client_for(world.a.slug).get(SITE).json()
    assert body["mode"] == "opening_soon"
    assert body["theme"]["primary_color"] == "#5B3FD9"


def test_active_without_any_page_is_opening_soon(world, client_for):
    body = client_for(world.b.slug).get(SITE).json()
    assert body["mode"] == "opening_soon"
    assert body["content"]["sections"][0]["title"] == "Birch College"


def test_public_site_archived_or_unknown_is_404(world, client_for):
    world.a.lifecycle_status = "archived"
    world.a.save()
    assert client_for(world.a.slug).get(SITE).status_code == 404
    assert client_for("nosuch").get(SITE).status_code == 404


@pytest.mark.parametrize("state,served", [("setup", True), ("active", True), ("suspended", False), ("archived", False)])
def test_public_asset_served_only_while_setup_or_active(world, admin_a, client_for, state, served):
    asset = admin_a.post("/api/v1/institution/site/assets", {"file": png()}, format="multipart").json()["id"]
    world.a.lifecycle_status = state
    world.a.save()
    response = client_for(None).get(f"/api/v1/public/assets/{asset}")
    assert (response.status_code == 200) is served
    if served:
        assert response["Content-Type"] == "image/png"
        assert response["Cache-Control"] == "public, max-age=31536000, immutable"
        assert response["X-Content-Type-Options"] == "nosniff"
