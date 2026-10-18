import pytest

from accounts.permissions import today_for
from configuration.models import SettingRevision
from testing import factories

BASE = "/api/v1/institution/settings"


@pytest.fixture
def admin(world, client_for):
    return client_for(world.a.slug, world.a_admin)


def test_list_and_detail(world, admin):
    items = admin.get(BASE).json()
    assert [item["key"] for item in items] == ["modules.enabled", "access.role_approval", "academic.year_start"]
    year = items[2]
    assert (year["value_now"], year["description_now"], year["scheduled"], year["open"]) == (
        6,
        "Starts in June",
        None,
        None,
    )
    assert admin.get(f"{BASE}/nope").status_code == 404
    detail = admin.get(f"{BASE}/modules.enabled").json()
    assert detail["needs_approval"] is False and detail["history"]["count"] == 0
    assert [c["key"] for c in detail["choices"]] == sorted(world.a.modules)


def test_draft_preview_submit_and_schedule(world, admin):
    draft = admin.post(f"{BASE}/academic.year_start/draft").json()["draft"]
    assert admin.post(f"{BASE}/academic.year_start/draft").json()["draft"]["id"] == draft["id"]  # Review Focus 3
    saved = admin.put(f"{BASE}/academic.year_start/draft", {"version": draft["version"], "value": 4}, format="json")
    assert saved.status_code == 200
    assert admin.put(f"{BASE}/academic.year_start/draft", {"version": draft["version"], "value": 5}).status_code == 409
    detail = admin.get(f"{BASE}/academic.year_start").json()
    assert detail["draft"]["value"] == 4 and detail["preview"][0].startswith("The ")
    version = detail["draft"]["version"]
    bad = admin.put(f"{BASE}/academic.year_start/draft", {"version": version, "value": 13}, format="json")
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "value"
    later = str(today_for(world.a).replace(year=today_for(world.a).year + 1))
    body = {"version": detail["draft"]["version"], "effective_from": later, "reason": "Board calendar"}
    published = admin.post(f"{BASE}/academic.year_start/draft/submit", body, format="json")
    assert published.status_code == 200
    after = admin.get(BASE).json()[2]
    assert after["value_now"] == 6 and after["scheduled"]["description"] == "Starts in April"
    assert admin.get(f"{BASE}/academic.year_start").json()["history"]["count"] == 1


def test_who_may_reach_settings(world, admin, client_for):
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.get(BASE).status_code == 403
    assert client_for(None, world.platform_admin).get(BASE).status_code == 404
    revision = SettingRevision.objects.create(
        institution=world.a,
        key="academic.year_start",
        number=1,
        value=4,
        status="published",
        effective_from=today_for(world.a),
    )
    birch = client_for(world.b.slug, world.b_admin)
    restore = f"{BASE}/academic.year_start/revisions/{revision.id}/restore"
    assert birch.post(restore, {"version": None}, format="json").status_code == 404


def test_own_institution_carries_modules_and_year(world, admin):
    body = admin.get("/api/v1/institution").json()
    assert body["modules_enabled"] == []
    assert body["academic_year"]["label"].count("–") == 1
    assert body["academic_year"]["starts_on"].endswith("-06-01")
