"""A new institution's first public page: sensible wording for its category that the admin then makes their own.
It states nothing as fact about the institution: no ratings, counts or quotes. People and testimonials start hidden
with placeholder text, and the gallery starts hidden until photos are added."""

SCHOOL_OFFERINGS = [
    ("Primary", "Grades 1 to 5: reading, numbers and curiosity, with plenty of play.", ["Grades 1–5"]),
    ("Middle school", "Grades 6 to 8: subjects taught by specialist teachers.", ["Grades 6–8"]),
    ("Secondary", "Grades 9 and 10: steady preparation for board examinations.", ["Grades 9–10"]),
]
HIGHER_OFFERINGS = {
    "college": [
        ("Arts", "Languages, history, economics and more.", ["Undergraduate"]),
        ("Commerce", "Accounting, business and finance.", ["Undergraduate"]),
        ("Science", "Physics, chemistry, mathematics and life sciences.", ["Undergraduate"]),
    ],
    "engineering_college": [
        ("Computer Science & Engineering", "Programming, systems and data, with lab work every semester.", ["B.Tech"]),
        ("Electronics & Communication", "Circuits, signals and embedded systems.", ["B.Tech"]),
        ("Mechanical Engineering", "Design, manufacturing and thermal sciences.", ["B.Tech"]),
    ],
    "university": [
        ("Undergraduate programmes", "Degree programmes across our schools and departments.", ["UG"]),
        ("Postgraduate programmes", "Master's programmes with advanced coursework and projects.", ["PG"]),
        ("Research", "Doctoral study under the guidance of faculty supervisors.", ["PhD"]),
    ],
}


def _image(alt: str) -> dict:
    return {"asset": None, "alt": alt}


def starter_content(display_name: str, category: str) -> dict:
    school = category == "school"
    audience = "parents" if school else "students"
    offerings = SCHOOL_OFFERINGS if school else HIGHER_OFFERINGS[category]
    ask = {"label": "Ask about this", "href": "#s-faq"}
    if school:
        steps = [
            ("Enquire", "Call or write to the school office with your questions.", "chat"),
            ("Visit", "See the classrooms and meet the teachers.", "home"),
            ("Apply", "Fill in the application form for your child.", "apply"),
            ("Join", "Confirm the admission and get ready for the first day.", "check"),
        ]
    else:
        steps = [
            ("Explore", "Find the programme that fits you.", "book"),
            ("Check eligibility", "Read the entry requirements for your programme.", "check"),
            ("Apply", "Send your application and documents.", "apply"),
            ("Enrol", "Accept your offer and register for your first term.", "award"),
        ]
    return {
        "sections": [
            {
                "id": "hero",
                "type": "hero",
                "visible": True,
                "eyebrow": "Admissions open · 2027–28",
                "title": f"Welcome to {display_name}",
                "subtitle": (
                    "Caring teachers, a safe campus and parents kept in the loop. "
                    "Come and see where your child will learn."
                    if school
                    else "Programmes taught by dedicated faculty, "
                    "with the support you need from your first day to your degree."
                ),
                "primary_cta": {"label": "How admission works", "href": "#s-steps"},
                "secondary_cta": {"label": "Common questions", "href": "#s-faq"},
                "images": [_image("Students in class"), _image("Our campus"), _image("Campus life")],
                "badge": None,
                "stickers": [],
            },
            {
                "id": "offerings",
                "type": "offerings",
                "visible": True,
                "eyebrow": "What we offer",
                "title": "Learning at every stage" if school else "Choose your programme",
                "items": [
                    {"title": title, "text": blurb, "image": _image(title), "tags": tags, "cta": ask}
                    for title, blurb, tags in offerings
                ],
            },
            {
                "id": "steps",
                "type": "steps",
                "visible": True,
                "eyebrow": "Admissions, start to finish",
                "title": "How admission works",
                "items": [{"title": title, "text": blurb, "icon": icon} for title, blurb, icon in steps],
            },
            {
                "id": "people",
                "type": "people",
                "visible": False,
                "eyebrow": "Our teachers" if school else "Our faculty",
                "title": "The people you will learn with",
                "items": [{"name": "Name", "role": "Subject", "photo": _image("Portrait"), "facts": ["A short fact"]}],
            },
            {
                "id": "gallery",
                "type": "gallery",
                "visible": False,
                "eyebrow": "Campus life",
                "title": "A look around",
                "images": [_image("Campus photo") for _ in range(4)],
            },
            {
                "id": "testimonials",
                "type": "testimonials",
                "visible": False,
                "eyebrow": "In their words",
                "title": f"Notes from our {audience}",
                "items": [
                    {"quote": f"A few words from one of our {audience}.", "name": "Name", "relation": "Relation"}
                ],
            },
            {
                "id": "visit",
                "type": "feature",
                "visible": True,
                "eyebrow": "Come and see us",
                "title": "Visit the campus",
                "text": "Our office is open on working days. Call or write to book a time to walk around the campus "
                "and meet our teachers.",
                "bullets": ["Meet the teachers", "See the classrooms and labs", "Ask about fees and transport"],
                "image": _image("Our campus"),
            },
            {
                "id": "faq",
                "type": "faq",
                "visible": True,
                "eyebrow": "FAQ",
                "title": f"Questions {audience} ask",
                "subtitle": "If yours isn't here, call or write to our office.",
                "items": [
                    {
                        "q": "When do admissions open?",
                        "a": "The admission schedule is announced by our office. "
                        "Contact us to hear when forms are available.",
                    },
                    {
                        "q": "Can we visit before applying?",
                        "a": "Yes. Call or write to the office to book a visit on a working day.",
                    },
                    {
                        "q": "Who do we contact with questions?",
                        "a": "Our office, by phone or email. The details are at the bottom of this page.",
                    },
                ],
            },
        ]
    }
