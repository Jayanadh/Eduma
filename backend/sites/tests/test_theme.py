import pytest

from sites.theme import BODY_FONTS, DEFAULT_THEME, HEADING_FONTS, contrast, derive, fill, readable_on, text_safe


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
        "primary_fill": "#4B5AE4",
        "on_primary": "#FFFFFF",
        "primary_text": "#4B5AE4",
        "secondary_fill": "#FFD43B",
        "on_secondary": "#17132B",
        "secondary_text": text_safe("#FFD43B"),
    }


@pytest.mark.parametrize("color", ["#E0393E", "#D9480F", "#1C7ED6", "#CF2AD5"])
def test_mid_tones_get_a_fill_that_text_can_sit_on(color):
    # Neither white nor ink reaches 4.5:1 on these, so text sits on a slightly darker fill instead.
    assert max(contrast("#FFFFFF", color), contrast("#17132B", color)) < 4.5
    theme = derive(color, color)
    assert theme["primary_fill"] != color
    assert contrast(theme["on_primary"], theme["primary_fill"]) >= 4.5
    assert contrast(theme["on_secondary"], theme["secondary_fill"]) >= 4.5


def test_fill_keeps_colours_that_already_work():
    assert fill("#4B5AE4") == "#4B5AE4"
    assert fill("#FFD43B") == "#FFD43B"


def test_defaults_are_known_fonts():
    assert DEFAULT_THEME == {
        "primary_color": "#4B5AE4",
        "secondary_color": "#FFD43B",
        "heading_font": "bricolage",
        "body_font": "dm-sans",
    }
    assert set(HEADING_FONTS) == {"bricolage", "fredoka", "jakarta", "space-grotesk", "fraunces", "playfair"}
    assert set(BODY_FONTS) == {"dm-sans", "inter", "nunito", "source-sans", "lora"}
