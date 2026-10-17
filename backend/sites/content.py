"""The public page's content: {"sections": [...]}, a fixed set of section types an admin can fill, hide and reorder.
Validated here so the page can never hold unsafe links, oversized lists or unknown fields."""

import json

from rest_framework import serializers

SECTION_TYPES = ("hero", "offerings", "steps", "people", "gallery", "testimonials", "feature", "faq")
STEP_ICONS = ("apply", "calendar", "chat", "book", "check", "star", "users", "home", "award", "map")
SAFE_LINK_PREFIXES = ("https://", "http://", "mailto:", "tel:", "#", "/")


def validate_href(value: str) -> str:
    """Web, email and phone links, anchors on the page and paths on this site; never javascript:, data: or //host."""
    if not value.startswith(SAFE_LINK_PREFIXES) or value.startswith("//"):
        raise serializers.ValidationError("Use a link starting with https://, mailto:, tel:, # or /.")
    return value


def text(limit: int, **kw):
    return serializers.CharField(max_length=limit, allow_blank=True, default="", **kw)


def short_list(limit: int, items: int):
    return serializers.ListField(child=serializers.CharField(max_length=limit), max_length=items, default=list)


class Cta(serializers.Serializer):
    label = serializers.CharField(max_length=30)
    href = serializers.CharField(max_length=500, validators=[validate_href])


class Image(serializers.Serializer):
    asset = serializers.UUIDField(required=False, allow_null=True, default=None)
    alt = text(120)


def optional(serializer_class):
    return serializer_class(required=False, allow_null=True, default=None)


class Section(serializers.Serializer):
    id = serializers.RegexField(r"^[a-z0-9-]{1,40}$")
    type = serializers.ChoiceField(SECTION_TYPES)
    visible = serializers.BooleanField(default=True)
    eyebrow = text(40)
    title = text(120)


class Badge(serializers.Serializer):
    value = serializers.CharField(max_length=12)
    label = text(24)


class Hero(Section):
    subtitle = text(300)
    primary_cta = Cta()
    secondary_cta = optional(Cta)
    images = Image(many=True, max_length=3, default=list)
    badge = optional(Badge)
    stickers = short_list(24, 2)


class Offering(serializers.Serializer):
    title = serializers.CharField(max_length=60)
    text = text(200)
    image = optional(Image)
    tags = short_list(20, 3)
    cta = optional(Cta)


class Offerings(Section):
    subtitle = text(300)
    items = Offering(many=True, max_length=6, default=list)


class Step(serializers.Serializer):
    title = serializers.CharField(max_length=40)
    text = text(160)
    icon = serializers.ChoiceField(STEP_ICONS, default="check")


class Steps(Section):
    items = Step(many=True, max_length=6, default=list)


class Person(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    role = text(60)
    photo = optional(Image)
    facts = short_list(80, 4)


class People(Section):
    subtitle = text(300)
    items = Person(many=True, max_length=6, default=list)


class Gallery(Section):
    images = Image(many=True, max_length=8, default=list)


class Testimonial(serializers.Serializer):
    quote = serializers.CharField(max_length=300)
    name = serializers.CharField(max_length=60)
    relation = text(60)
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True, default=None)
    photo = optional(Image)


class Testimonials(Section):
    items = Testimonial(many=True, max_length=6, default=list)


class Feature(Section):
    text = text(400)
    bullets = short_list(80, 5)
    image = optional(Image)
    cta = optional(Cta)


class Question(serializers.Serializer):
    q = serializers.CharField(max_length=160)
    a = serializers.CharField(max_length=600)


class Faq(Section):
    subtitle = text(300)
    cta = optional(Cta)
    items = Question(many=True, max_length=12, default=list)


SERIALIZERS = {
    "hero": Hero,
    "offerings": Offerings,
    "steps": Steps,
    "people": People,
    "gallery": Gallery,
    "testimonials": Testimonials,
    "feature": Feature,
    "faq": Faq,
}


def validate_content(data) -> dict:
    """Checks and normalises page content; raises ValidationError with paths such as sections.2.items.0.cta.href."""
    sections = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(sections, list):
        raise serializers.ValidationError({"sections": ["Send the page sections as a list."]})
    errors, cleaned = [], []
    for raw in sections:
        kind = raw.get("type") if isinstance(raw, dict) else None
        serializer = SERIALIZERS.get(kind, Section)(data=raw)
        if serializer.is_valid() and kind in SERIALIZERS:
            cleaned.append(serializer.validated_data)
            errors.append({})
        else:
            errors.append(serializer.errors or {"type": ["Unknown section type."]})
    if any(errors):
        raise serializers.ValidationError({"sections": errors})
    types = [section["type"] for section in cleaned]
    if not cleaned or types[0] != "hero" or not cleaned[0]["visible"]:
        raise serializers.ValidationError(
            {"sections": ["The page starts with the hero section, which cannot be hidden."]}
        )
    if len(set(types)) != len(types):
        raise serializers.ValidationError({"sections": ["Each kind of section can appear only once."]})
    # Plain JSON (UUIDs as strings), ready to store.
    return json.loads(json.dumps({"sections": cleaned}, default=str))


def referenced_assets(content: dict) -> set[str]:
    """Every image asset id used anywhere in the content."""
    found = set()

    def walk(value):
        if isinstance(value, dict):
            if value.get("asset"):
                found.add(str(value["asset"]))
            for inner in value.values():
                walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    walk(content)
    return found
