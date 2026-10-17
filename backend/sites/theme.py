"""Brand colours and fonts, and the readable colours derived from them. An institution picks any primary and secondary
colour; the server works out which text colour sits on each (white or ink) and, for coloured text and links on white, a
darker shade that still reaches WCAG AA (4.5:1). Semantic colours (error, success...) are not themeable."""

import colorsys

INK = "#17132B"
WHITE = "#FFFFFF"

HEADING_FONTS = {
    "bricolage": "Bricolage Grotesque",
    "fredoka": "Fredoka",
    "jakarta": "Plus Jakarta Sans",
    "space-grotesk": "Space Grotesk",
    "fraunces": "Fraunces",
    "playfair": "Playfair Display",
}
BODY_FONTS = {
    "dm-sans": "DM Sans",
    "inter": "Inter",
    "nunito": "Nunito",
    "source-sans": "Source Sans 3",
    "lora": "Lora",
}
# Eduma's own theme: the indigo of the logo and a warm yellow.
DEFAULT_THEME = {
    "primary_color": "#4B5AE4",
    "secondary_color": "#FFD43B",
    "heading_font": "bricolage",
    "body_font": "dm-sans",
}


def _rgb(color: str) -> tuple[float, float, float]:
    value = color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _luminance(color: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG 2.x contrast ratio, 1 to 21."""
    lighter, darker = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def readable_on(color: str) -> str:
    """White or ink, whichever is easier to read on `color`. One of them always reaches 4.5:1."""
    return WHITE if contrast(WHITE, color) >= contrast(INK, color) else INK


def text_safe(color: str, background: str = WHITE, target: float = 4.5) -> str:
    """`color` itself if it is readable as text on `background`, otherwise the same hue darkened step by step."""
    color = color.upper()
    hue, lightness, saturation = colorsys.rgb_to_hls(*_rgb(color))
    while contrast(color, background) < target and lightness > 0:
        lightness = max(0.0, lightness - 0.02)
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        color = "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))
    return color


def derive(primary: str, secondary: str) -> dict:
    return {
        "on_primary": readable_on(primary),
        "primary_text": text_safe(primary),
        "on_secondary": readable_on(secondary),
        "secondary_text": text_safe(secondary),
    }
