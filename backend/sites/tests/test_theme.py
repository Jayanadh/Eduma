import pytest

from sites.theme import BODY_FONTS, DEFAULT_THEME, HEADING_FONTS, contrast, derive, readable_on, text_safe


def test_contrast_known_pairs():
    assert contrast("#FFFFFF", "#000000") == pytest.approx(21.0)
    assert contrast("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.01)
    assert contrast("#4B5AE4", "#FFFFFF") == pytest.approx(5.41, abs=0.02)
    assert contrast("#4b5ae4", "#ffffff") == contrast("#FFFFFF", "#4B5AE4")


def test_readable_on():
    assert readable_on("#4B5AE4") == "#FFFFFF"
    assert readable_on("#FFD43B") == "#17132B"
    assert readable_on("#000000") == "#FFFFFF"


def test_text_safe_darkens_only_when_needed():
    assert text_safe("#4B5AE4") == "#4B5AE4"
    darker = text_safe("#FFD43B")
    assert contrast(darker, "#FFFFFF") >= 4.5
    assert darker != "#FFD43B"
    assert darker.startswith("#") and len(darker) == 7 and darker == darker.upper()
    assert contrast(text_safe("#FFFFFF"), "#FFFFFF") >= 4.5


def test_derive():
    assert derive("#4B5AE4", "#FFD43B") == {
        "on_primary": "#FFFFFF",
        "primary_text": "#4B5AE4",
        "on_secondary": "#17132B",
        "secondary_text": text_safe("#FFD43B"),
    }


def test_defaults_are_known_fonts():
    assert DEFAULT_THEME == {
        "primary_color": "#4B5AE4",
        "secondary_color": "#FFD43B",
        "heading_font": "bricolage",
        "body_font": "dm-sans",
    }
    assert set(HEADING_FONTS) == {"bricolage", "fredoka", "jakarta", "space-grotesk", "fraunces", "playfair"}
    assert set(BODY_FONTS) == {"dm-sans", "inter", "nunito", "source-sans", "lora"}
