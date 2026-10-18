import copy

import pytest
from django.core.exceptions import ValidationError

from common.models import AuditEvent
from institutions.modules import MODULES, check_modules, default_modules

from .test_onboarding import PAYLOAD, URL, create


@pytest.fixture
def platform(world, client_for):
    return client_for(None, world.platform_admin)


def test_defaults_follow_category():
    assert "report_cards" in default_modules("school")
    assert "report_cards" not in default_modules("college")
    categories = ("school", "college", "engineering_college", "university")
    assert [c for c in categories if "affiliations" in default_modules(c)] == ["university"]
    assert not any("library" in default_modules(c) for c in categories)
    assert default_modules("school") == sorted(default_modules("school"))


def test_dependencies_and_unknown_keys():
    with pytest.raises(ValidationError, match="Attendance needs Academic structure and timetable."):
        check_modules(["attendance"])
    with pytest.raises(ValidationError, match="Unknown module: nope."):
        check_modules(["nope"])
    assert check_modules(["students", "students", "fees"]) == ["fees", "students"]
    for category in ("school", "college", "engineering_college", "university"):
        assert check_modules(default_modules(category)) == default_modules(category)


def test_create_uses_defaults_and_patch_is_versioned_and_audited(world, platform):
    created = create(platform).json()
    assert created["modules"] == default_modules("school")
    url = f"{URL}/{created['id']}"
    chosen = ["library", "students"]
    saved = platform.patch(url, {"version": created["version"], "modules": chosen})
    assert saved.status_code == 200 and saved.json()["modules"] == chosen
    event = AuditEvent.objects.filter(action="institution.updated").latest("at")
    assert event.changes["modules"] == {"from": default_modules("school"), "to": chosen}
    bad = platform.patch(url, {"version": saved.json()["version"], "modules": ["fees"]})
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "modules"
    assert platform.patch(url, {"version": created["version"], "modules": chosen}).status_code == 409


def test_create_accepts_a_chosen_list(world, platform):
    body = copy.deepcopy(PAYLOAD)
    body["modules"] = ["students", "admissions"]
    response = platform.post(URL, body, format="json", HTTP_IDEMPOTENCY_KEY="7d3c4e1e-6a39-4bb5-9a6f-3c1c4b6b9f01")
    assert response.status_code == 201, response.json()
    assert response.json()["modules"] == ["admissions", "students"]


def test_catalogue_is_platform_only(world, platform, client_for):
    catalogue = platform.get("/api/v1/platform/modules").json()
    assert len(catalogue) == len(MODULES) == 20
    assert catalogue[0] == {
        "key": "admissions",
        "label": "Admissions and enrollment",
        "group": "core",
        "depends_on": ["students"],
        "default_for": ["college", "engineering_college", "school", "university"],
        "available": True,
    }
    assert client_for(world.a.slug, world.a_admin).get("/api/v1/platform/modules").status_code == 404
