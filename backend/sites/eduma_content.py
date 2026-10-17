"""The Eduma main page, kept in code. It describes only what Eduma is and where it is heading; nothing on it claims a
module is live before it is, and there are no figures."""

import copy

from django.conf import settings

TALK = {"label": "Talk to us", "href": "mailto:"}  # the address is filled in per request from EDUMA_CONTACT_EMAIL

EDUMA_CONTENT = {
    "sections": [
        {
            "id": "hero", "type": "hero", "visible": True,
            "eyebrow": "From schools to universities",
            "title": "One calm home for your whole institution.",
            "subtitle": (
                "Admissions, academics, fees and parent communication in one place, on a site that carries your "
                "institution's own name, logo and colours."
            ),
            "primary_cta": TALK,
            "secondary_cta": {"label": "How it works", "href": "#s-steps"},
            "images": [
                {"asset": None, "alt": "Your institution's branded page"},
                {"asset": None, "alt": "The admin workspace"},
                {"asset": None, "alt": "The site editor"},
            ],
            "badge": None,
            "stickers": ["Your logo, your colours", "Your own web address"],
        },
        {
            "id": "offerings", "type": "offerings", "visible": True,
            "eyebrow": "Who it's for",
            "title": "Built for four kinds of institution",
            "subtitle": "Each keeps its own way of working: grades and sections, or programmes, credits and terms.",
            "items": [
                {"title": "Schools", "text": "Grades and sections, report cards, and parents kept close.",
                 "image": None, "tags": ["Grades", "Parents"], "cta": TALK},
                {"title": "Colleges", "text": "Programmes, semesters, course registration and transcripts.",
                 "image": None, "tags": ["Credits", "Semesters"], "cta": TALK},
                {"title": "Engineering colleges", "text": "Theory and lab courses, projects and outcome evidence.",
                 "image": None, "tags": ["Labs", "Projects"], "cta": TALK},
                {"title": "Universities", "text": "Departments and campuses, central examinations and affiliated colleges.",
                 "image": None, "tags": ["Campuses", "Affiliation"], "cta": TALK},
            ],
        },
        {
            "id": "steps", "type": "steps", "visible": True,
            "eyebrow": "Getting started",
            "title": "From hello to your own Eduma site",
            "items": [
                {"title": "We set you up", "text": "We create your institution and its first administrator.",
                 "icon": "home"},
                {"title": "Your address", "text": "Your institution gets its own web address on Eduma.", "icon": "map"},
                {"title": "Make it yours", "text": "Add your logo, colours, fonts, words and photos.", "icon": "star"},
                {"title": "Go live", "text": "Publish your page and invite your team to sign in.", "icon": "check"},
            ],
        },
        {
            "id": "direction", "type": "feature", "visible": True,
            "eyebrow": "Where we're heading",
            "title": "Teachers and parents, on the same page",
            "text": (
                "Teacher–parent messages and calls, and teacher-led online classes, are part of the Eduma plan. They "
                "are being built now and will be switched on for each institution when they are ready."
            ),
            "bullets": [
                "Only a child's own parents can contact their teachers",
                "Students join classes their teacher hosts",
                "Recording stays off unless your institution approves it",
            ],
            "image": None,
            "cta": TALK,
        },
        {
            "id": "faq", "type": "faq", "visible": True,
            "eyebrow": "FAQ",
            "title": "Questions institutions ask",
            "subtitle": "If yours isn't here, write to us.",
            "cta": TALK,
            "items": [
                {"q": "Is Eduma available now?",
                 "a": "Institution sites, branding and administrator sign-in are ready. Admissions, academics, fees and "
                      "communication are being built and will be switched on as each one is finished."},
                {"q": "Can our site look like our institution?",
                 "a": "Yes. Your page and your workspace use your logo, your colours and your choice of fonts, and you "
                      "decide what your page says."},
                {"q": "Who can sign in?",
                 "a": "Only the people your institution adds. Each institution signs in at its own address."},
                {"q": "Is our data kept apart from other institutions?",
                 "a": "Yes. Every institution's records are kept separate. Hosting and retention terms are agreed with "
                      "each institution before it goes live."},
                {"q": "How do we start?",
                 "a": "Write to us. We set up your institution, give you your web address and hand your administrator "
                      "their first sign-in."},
            ],
        },
    ]
}


def eduma_content() -> dict:
    """EDUMA_CONTENT with the contact address from the settings, as served to visitors."""
    content = copy.deepcopy(EDUMA_CONTENT)
    href = f"mailto:{settings.EDUMA_CONTACT_EMAIL}"

    def fill(value):
        if isinstance(value, dict):
            if value.get("href") == "mailto:":
                value["href"] = href
            for inner in value.values():
                fill(inner)
        elif isinstance(value, list):
            for inner in value:
                fill(inner)

    fill(content)
    return content
