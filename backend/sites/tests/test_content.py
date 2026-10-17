import copy
import re

import pytest
from rest_framework.exceptions import ValidationError

from common.exceptions import flatten_errors
from institutions.models import Category
from sites.content import referenced_assets, validate_content, validate_href
from sites.eduma_content import EDUMA_CONTENT, eduma_content
from sites.starter import starter_content


def hero(**kw):
    return {"id": "hero", "type": "hero", "visible": True, "title": "Hello",
            "primary_cta": {"label": "Visit", "href": "#s-faq"}, **kw}


def faq(n=1, **kw):
    return {"id": "faq", "type": "faq", "visible": True, "title": "FAQ",
            "items": [{"q": f"Q{i}", "a": "A"} for i in range(n)], **kw}


def fields(data) -> list[str]:
    with pytest.raises(ValidationError) as caught:
        validate_content(data)
    return [error["field"] for error in flatten_errors(caught.value.detail)]


def test_minimal_content_is_valid_and_normalised():
    result = validate_content({"sections": [hero()]})
    assert result["sections"][0]["images"] == []
    assert result["sections"][0]["eyebrow"] == ""


def test_hero_must_be_first_and_visible():
    assert fields({"sections": [faq(), hero()]}) == ["sections"]
    assert fields({"sections": [hero(visible=False)]}) == ["sections"]
    assert fields({"sections": []}) == ["sections"]


def test_duplicate_section_type_rejected():
    assert fields({"sections": [hero(), faq(), faq(id="faq-2")]}) == ["sections"]


def test_unknown_section_type_rejected():
    assert "sections.1.type" in fields({"sections": [hero(), {"id": "x", "type": "pricing", "title": "T"}]})


@pytest.mark.parametrize("href", ["javascript:alert(1)", "data:text/html,x", "//evil.com", "ftp://x", " JavaScript:1"])
def test_unsafe_hrefs_rejected(href):
    assert "sections.0.primary_cta.href" in fields({"sections": [hero(primary_cta={"label": "Go", "href": href})]})


@pytest.mark.parametrize("href", ["https://a.example", "http://a.example", "mailto:a@b.c", "tel:+919", "#s-faq", "/login"])
def test_safe_hrefs_allowed(href):
    assert validate_href(href) == href


def test_item_limits():
    offerings = {"id": "offer", "type": "offerings", "title": "T", "items": [{"title": f"O{i}"} for i in range(7)]}
    assert "sections.1.items" in fields({"sections": [hero(), offerings]})
    validate_content({"sections": [hero(), faq(12)]})
    assert "sections.1.items" in fields({"sections": [hero(), faq(13)]})
    assert "sections.0.images" in fields({"sections": [hero(images=[{"alt": "x"}] * 4)]})


def test_nested_paths_point_at_the_field():
    bad = faq(2)
    bad["items"][1]["q"] = "x" * 161
    assert fields({"sections": [hero(), bad]}) == ["sections.1.items.1.q"]


def test_referenced_assets_finds_every_image():
    content = validate_content({"sections": [
        hero(images=[{"asset": "8c5e9a52-8d2c-4f63-9d3a-2e7f2b7a2d11", "alt": "a"}, {"alt": "empty"}]),
        {"id": "gallery", "type": "gallery", "title": "G", "images": [{"asset": "1d2e3f40-0000-4000-8000-000000000001"}]},
    ]})
    assert referenced_assets(content) == {"8c5e9a52-8d2c-4f63-9d3a-2e7f2b7a2d11", "1d2e3f40-0000-4000-8000-000000000001"}


def test_validated_content_is_plain_json():
    content = validate_content({"sections": [hero(images=[{"asset": "8c5e9a52-8d2c-4f63-9d3a-2e7f2b7a2d11"}])]})
    assert isinstance(content["sections"][0]["images"][0]["asset"], str)


@pytest.mark.parametrize("category", Category.values)
def test_starter_content_is_valid_with_people_and_testimonials_hidden(category):
    content = validate_content(starter_content("Aster School", category))
    visible = {section["type"]: section["visible"] for section in content["sections"]}
    assert visible["people"] is False and visible["testimonials"] is False
    hero_section = content["sections"][0]
    assert not re.search(r"\d", hero_section["title"])  # no invented metrics
    assert hero_section.get("badge") is None


def test_eduma_content_is_valid_and_has_no_numbers():
    validate_content(EDUMA_CONTENT)
    text = str(EDUMA_CONTENT)
    assert "★" not in text


def test_eduma_contact_is_filled_at_request_time(settings):
    settings.EDUMA_CONTACT_EMAIL = "team@eduma.example"
    content = eduma_content()
    assert content["sections"][0]["primary_cta"]["href"] == "mailto:team@eduma.example"
    assert EDUMA_CONTENT["sections"][0]["primary_cta"]["href"] == "mailto:"  # the constant is not mutated
    assert copy.deepcopy(content) == content


def test_eduma_page_names_all_four_institution_types():
    offerings = next(s for s in EDUMA_CONTENT["sections"] if s["type"] == "offerings")
    assert [item["title"] for item in offerings["items"]] == [
        "Schools", "Colleges", "Engineering colleges", "Universities",
    ]
