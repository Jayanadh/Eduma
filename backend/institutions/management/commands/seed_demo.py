"""Demo data for a laptop: the platform admin and four made-up institutions, one per category, each with its own look,
and at Aster a second campus, departments and staff with different roles. Safe to run again: nothing is duplicated
and the demo passwords are put back. Refuses to run with DEBUG off."""

import datetime as dt
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import CustomRole, Membership, RoleAssignment, User
from accounts.permissions import today_for
from institutions import services
from institutions.models import Institution, LifecycleStatus
from institutions.modules import default_modules
from organization.models import Campus, Department
from sites import services as site_services

PASSWORD = "Demo-pass-2026"
DEMO_DOMAIN = "www.meridiancollege.localhost"
# Aster's staff: login ID, name, built-in role key or custom role name, scope code (None: the whole institution).
ASTER_STAFF = [
    ("aster.principal", "Aster Principal", "principal", None),
    ("aster.campus", "Aster City Campus Admin", "campus_admin", "CITY"),
    ("aster.teacher", "Aster Science Teacher", "teacher", "SCI"),
    ("aster.office", "Aster Front Office", "Front office", "CITY"),
    ("aster.deputy", "Aster Deputy Admin", "institution_admin", None),
    ("aster.admissions", "Aster Admissions Officer", "admissions_officer", None),
    ("aster.registrar", "Aster Registrar", "registrar", None),
]

# slug, display name, legal name, category, active?, (primary, secondary, heading font, body font)
DEMO = [
    ("aster", "Aster School", "Aster Educational Society", "school", True,
     ("#5B3FD9", "#FFC93C", "fredoka", "nunito")),
    ("meridian", "Meridian College", "Meridian College Trust", "college", True,
     ("#0F766E", "#F9A8D4", "fraunces", "source-sans")),
    ("vector", "Vector Engineering College", "Vector Institute of Technology Society", "engineering_college", False,
     ("#1D4ED8", "#FDE047", "space-grotesk", "inter")),
    ("summit", "Summit University", "Summit University", "university", True,
     ("#7C2D12", "#FCD34D", "playfair", "lora")),
]  # fmt: skip


class Command(BaseCommand):
    help = "Create (or refresh) the Eduma demo data. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo is for development: it runs only with DEBUG on.")
        platform_admin = self._platform_admin()
        for number, (slug, name, legal, category, active, theme) in enumerate(DEMO, start=1):
            institution = self._institution(platform_admin, number, slug, name, legal, category)
            admin = services.first_admin(institution)
            admin.set_password(PASSWORD)
            admin.must_change_password = not active
            if active and admin.last_login is None:
                admin.last_login = timezone.now()
            admin.save()
            if not institution.site_revisions.filter(status="published").exists():
                self._style(institution, platform_admin, theme, publish=active)
            if active and institution.lifecycle_status == LifecycleStatus.SETUP:
                services.transition(
                    institution.pk,
                    platform_admin,
                    to=LifecycleStatus.ACTIVE,
                    reason="Demo data",
                    version=institution.version,
                )
        for institution in Institution.objects.filter(modules=[]):
            institution.modules = default_modules(institution.category)
            institution.save(update_fields=["modules"])
        self._aster_staff(platform_admin)
        self._aster_settings()
        self._aster_admissions()
        self._aster_families()
        self._aster_employees()
        self._aster_enquiries()
        self._aster_academics()
        self._meridian_academics(platform_admin)
        self._meridian_registration(platform_admin)
        self._affiliation(platform_admin)
        self._timetable()
        self._results(platform_admin)
        self._fees(platform_admin)
        self._communication()
        self._campus(platform_admin)
        self._staff_services(platform_admin)
        self._development(platform_admin)
        # One institution on a domain of its own; browsers send any *.localhost name to this machine.
        Institution.objects.filter(slug="meridian", custom_domain="").update(custom_domain=DEMO_DOMAIN)
        self.stdout.write(self.style.SUCCESS(f"Demo data ready. Every demo login uses the password {PASSWORD}."))

    def _platform_admin(self) -> User:
        admin, _ = User.objects.get_or_create(
            username="eduma.admin", defaults={"full_name": "Eduma Platform Admin", "is_platform_admin": True}
        )
        admin.full_name, admin.is_platform_admin, admin.must_change_password = "Eduma Platform Admin", True, False
        admin.set_password(PASSWORD)
        admin.save()
        return admin

    def _institution(self, actor, number, slug, name, legal, category) -> Institution:
        data = {
            "slug": slug, "legal_name": legal, "display_name": name, "category": category,
            "contact_email": f"office@{slug}.example", "contact_phone": f"+91 90000 0000{number}",
            "address": f"{number} Lake Road, Vijayawada, Andhra Pradesh",
            "admin": {"full_name": f"{name} Admin", "username": f"{slug}.admin", "password": PASSWORD},
        }  # fmt: skip
        key, digest = uuid.uuid5(uuid.NAMESPACE_DNS, f"{slug}.eduma.demo"), services.request_digest(data)
        return services.replayed(key, digest) or services.create_institution(actor, data, key, digest)[0]

    def _style(self, institution, actor, theme, publish: bool) -> None:
        primary, secondary, heading, body = theme
        draft = site_services.get_or_create_draft(institution, actor)
        draft = site_services.save_draft(institution, actor, draft.version, {
            "primary_color": primary, "secondary_color": secondary, "heading_font": heading, "body_font": body,
            "logo": None, "content": draft.content,
        })  # fmt: skip
        if publish:
            site_services.publish(institution, actor, draft.version)

    def _aster_staff(self, actor) -> None:
        aster = Institution.objects.get(slug="aster")

        def place(model, code, **defaults):
            return model.objects.get_or_create(institution=aster, code=code, defaults=defaults)[0]

        main = place(Campus, "MAIN", name="Main campus")
        city = place(Campus, "CITY", name="City campus")
        sci = place(Department, "SCI", name="Science", campus=main)
        place(Department, "PHY", name="Physics", campus=main, parent=sci)
        place(Department, "LANG", name="Languages", campus=main)
        front, _ = CustomRole.objects.get_or_create(
            institution=aster, name="Front office", defaults={"permissions": ["membership.read"], "created_by": actor}
        )
        scopes = {"CITY": city, "SCI": sci}
        for username, full_name, role, scope_code in ASTER_STAFF:
            custom = front if role == front.name else None
            self._member(aster, actor, username, full_name, "" if custom else role, scopes.get(scope_code), custom)

    def _member(self, institution, actor, username, full_name, role_key, scope, custom_role=None) -> Membership:
        """A staff login with the demo password and one role at `scope` (None: the whole institution)."""
        person, _ = User.objects.get_or_create(
            username=username, defaults={"full_name": full_name, "created_by": actor}
        )
        person.set_password(PASSWORD)
        person.must_change_password = False
        person.last_login = person.last_login or timezone.now()
        person.save()
        membership, _ = Membership.objects.get_or_create(
            institution=institution, user=person, defaults={"created_by": actor}
        )
        if not membership.assignments.exists():
            kind = "institution" if scope is None else "campus" if isinstance(scope, Campus) else "department"
            RoleAssignment.objects.create(
                membership=membership,
                institution=institution,
                role_key=role_key,
                custom_role=custom_role,
                scope_type=kind,
                campus=scope if kind == "campus" else None,
                department=scope if kind == "department" else None,
                starts_on=today_for(institution),
                created_by=actor,
            )
        return membership

    def _switch_on(self, institution, admin, *keys) -> None:
        """Modules switched on through the same steps an admin takes."""
        from configuration import services as settings_services
        from configuration.registry import setting

        modules = setting(institution, "modules.enabled")
        if set(keys) <= set(modules):
            return
        draft = settings_services.open_draft(institution, admin, "modules.enabled")
        value = sorted({*modules, *keys})
        draft = settings_services.save_draft(institution, admin, "modules.enabled", draft.version, value)
        settings_services.submit(
            institution, admin, "modules.enabled", draft.version, today_for(institution), "Demo data"
        )

    def _aster_settings(self) -> None:
        """Aster has switched on Admissions, Students and Academics, through the same steps an admin takes."""
        from configuration import services as settings_services

        aster = Institution.objects.get(slug="aster")
        if aster.settings.filter(key="modules.enabled").exists():
            return
        admin = User.objects.get(username="aster.admin")
        draft = settings_services.open_draft(aster, admin, "modules.enabled")
        draft = settings_services.save_draft(
            aster, admin, "modules.enabled", draft.version, ["academics", "admissions", "students"]
        )
        settings_services.submit(aster, admin, "modules.enabled", draft.version, today_for(aster), "Demo data")

    def _aster_admissions(self) -> None:
        """An open cycle, a parent with one submitted application and one child already enrolled, made through the
        same steps families and staff take."""
        import datetime as dt
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from admissions import applications, cycles, documents, enrollment, review

        aster = Institution.objects.get(slug="aster")
        if aster.cycles.exists():
            return
        admin = User.objects.get(username="aster.admin")
        registrar = User.objects.get(username="aster.registrar")
        main = aster.campuses.get(code="MAIN")
        today = today_for(aster)
        cycle = cycles.save_cycle(aster, admin, None, {
            "name": f"Admissions {today.year + 1}", "entry_year": today.year + 1, "opens_on": today,
            "closes_on": today + dt.timedelta(days=60), "instructions": "Apply before the closing date.",
            "places": [
                {"code": "C1", "label": "Class 1", "campus": main, "seats": 40},
                {"code": "C6", "label": "Class 6", "campus": main, "seats": 10},
            ],
            "questions": [
                {"code": "LANG", "label": "Home language", "help": "", "kind": "text", "options": [], "required": True},
                {"code": "BUS", "label": "Needs the school bus?", "help": "", "kind": "yes_no", "options": [],
                 "required": True},
            ],
            "documents": [
                {"code": "BIRTH", "label": "Birth certificate", "help": "", "required": True},
                {"code": "PHOTO", "label": "Recent photo", "help": "", "required": True},
            ],
        })  # fmt: skip
        cycle = cycles.publish(admin, cycle, cycle.version)
        parent, _ = User.objects.get_or_create(username="aster.parent", defaults={"full_name": "Aster Demo Parent"})
        parent.set_password(PASSWORD)
        parent.save()
        Membership.objects.get_or_create(institution=aster, user=parent, defaults={"kind": Membership.Kind.APPLICANT})
        buffer = io.BytesIO()
        Image.new("RGB", (60, 60), (91, 63, 217)).save(buffer, format="PNG")
        files = {"BIRTH": (b"%PDF-1.4\n%%EOF\n", "birth-certificate.pdf"), "PHOTO": (buffer.getvalue(), "photo.png")}
        made = []
        for learner, place in (
            ("Meera Demo", cycle.places.get(code="C1")),
            ("Arjun Demo", cycle.places.get(code="C6")),
        ):
            application = applications.start(parent, aster, cycle.id, place.id)
            application = applications.edit(parent, application, application.version, {
                "learner_name": learner, "date_of_birth": dt.date(today.year - 6, 5, 17),
                "guardian_name": parent.full_name,
                "guardian_relationship": "Parent", "guardian_phone": "+91 90000 00009", "address": "1 Lake Road",
                "answers": {"LANG": "Telugu", "BUS": True},
            })  # fmt: skip
            for code, (content, name) in files.items():
                documents.upload(parent, application, code, SimpleUploadedFile(name, content))
            application.refresh_from_db()
            made.append(applications.submit(parent, application, application.version))
        arjun = made[1]
        for step in (review.start_review, review.mark_eligible):
            arjun = step(registrar, arjun, arjun.version)
        arjun = review.offer(registrar, arjun, arjun.version, today + dt.timedelta(days=14))
        arjun = applications.accept(parent, arjun, arjun.version)
        student = enrollment.enroll(registrar, arjun, arjun.version, PASSWORD)
        student.user.must_change_password = False
        student.user.last_login = timezone.now()
        student.user.save()

    def _aster_families(self) -> None:
        """Arjun's parent verified with record access; his grandmother with her own login and nothing shared."""
        from students import guardians

        aster = Institution.objects.get(slug="aster")
        student = aster.students.filter(application__learner_name="Arjun Demo").first()
        if student is None:
            return
        registrar = User.objects.get(username="aster.registrar")
        evidence = {"authority_basis": "parent", "verification_method": "documents_in_person"}
        parent = student.guardian_links.filter(user__username="aster.parent").first()
        if parent is None:
            parent = guardians.propose_from_application(registrar, student, student.application)
        if parent.status == "proposed":
            guardians.verify(
                registrar, parent, parent.version, {**evidence, "verification_reference": "Seen at admission"}
            )
        if not student.guardian_links.filter(adult__full_name="Lakshmi Demo").exists():
            grandmother = guardians.propose(registrar, student, {"full_name": "Lakshmi Demo"}, "Grandmother")
            login = {"username": "aster.grandparent", "password": PASSWORD}
            guardians.verify(
                registrar,
                grandmother,
                grandmother.version,
                {**evidence, "authority_basis": "other", "access": {"record": False}, "login": login},
            )
        grandparent = User.objects.get(username="aster.grandparent")
        grandparent.set_password(PASSWORD)
        grandparent.must_change_password = False
        grandparent.save()

    def _aster_employees(self) -> None:
        from accounts.models import Employee

        aster = Institution.objects.get(slug="aster")
        staff = aster.memberships.filter(kind=Membership.Kind.STAFF, employee__isnull=True).order_by("user__username")
        # New staff in a later seed run continue the numbering instead of reusing AST-001.
        taken = Employee.objects.filter(institution=aster).count()
        for number, membership in enumerate(staff, start=taken + 1):
            Employee.objects.create(
                institution=aster,
                membership=membership,
                employee_number=f"AST-{number:03d}",
                joined_on=dt.date(2024, 6, 1),
            )

    def _aster_enquiries(self) -> None:
        """One question from the website, one walk-in being followed up (sample import file:
        backend/imports/fixtures/aster-students-sample.csv)."""
        from admissions import enquiries

        aster = Institution.objects.get(slug="aster")
        if aster.enquiries.exists():
            return
        officer = User.objects.get(username="aster.admissions")
        question = {"contact_name": "Ravi Kumar", "phone": "+91 90000 11111", "learner_name": "Kiran"}
        enquiries.create(aster, {**question, "message": "Is there a school bus to Benz Circle?"}, "website")
        walk_in = enquiries.create(
            aster,
            {
                "contact_name": "Priya Nair",
                "phone": "+91 90000 22222",
                "learner_name": "Anika",
                "message": "Class 6 fees",
            },
            "walk_in",
            actor=officer,
        )
        enquiries.add_follow_up(
            officer,
            walk_in,
            {
                "how": "phone",
                "note": "Sent the fee sheet; will call after the open day.",
                "next_follow_up_on": today_for(aster),
            },
        )

    def _aster_academics(self) -> None:
        """Academics switched on; 2026–27 (current) and 2027–28 with two terms each; Classes 1–10; four subjects;
        sections 6A and 6B this year, 6A and 7A next; aster.teacher teaching Science; Arjun in next year's 6A."""
        import datetime as dt

        from academics import placement, sections, structure
        from academics.models import GradeLevel, Subject

        aster = Institution.objects.get(slug="aster")
        admin = User.objects.get(username="aster.admin")
        self._switch_on(aster, admin, "academics")
        if aster.academic_years.exists():
            return
        years = {}
        for code, start, status in (("2026–27", 2026, "current"), ("2027–28", 2027, "planned")):
            data = {
                "code": code,
                "starts_on": dt.date(start, 6, 1),
                "ends_on": dt.date(start + 1, 3, 31),
                "status": status,
            }
            years[code] = year = structure.save_year(admin, aster, None, data)
            for ordinal, (begins, ends) in enumerate(
                ((dt.date(start, 6, 1), dt.date(start, 10, 31)), (dt.date(start, 11, 1), dt.date(start + 1, 3, 31))), 1
            ):
                structure.save_term(
                    admin,
                    year,
                    None,
                    {"name": f"Term {ordinal}", "ordinal": ordinal, "starts_on": begins, "ends_on": ends},
                )
        grades = {
            n: structure.save_named(admin, aster, GradeLevel, None, {"code": f"C{n}", "name": f"Class {n}", "order": n})
            for n in range(1, 11)
        }
        science = None
        for code, name in (("ENG", "English"), ("MATH", "Mathematics"), ("SCI", "Science"), ("TEL", "Telugu")):
            subject = structure.save_named(admin, aster, Subject, None, {"code": code, "name": name})
            science = subject if code == "SCI" else science
        main = aster.campuses.get(code="MAIN")
        teacher = Membership.objects.get(institution=aster, user__username="aster.teacher")
        made = {}
        for year_code, code, grade in (
            ("2026–27", "6A", 6),
            ("2026–27", "6B", 6),
            ("2027–28", "6A", 6),
            ("2027–28", "7A", 7),
        ):
            data = {
                "year": years[year_code].id,
                "grade": grades[grade].id,
                "campus": main.id,
                "code": code,
                "capacity": 40,
            }
            made[(year_code, code)] = sections.save_section(admin, aster, None, data)
        this_6a, next_6a = made[("2026–27", "6A")], made[("2027–28", "6A")]
        sections.save_section(admin, aster, this_6a, {"class_teacher": teacher.id}, this_6a.version)
        for section in (this_6a, next_6a):
            sections.assign_teacher(admin, section, teacher.id, science.id)
        arjun = aster.students.filter(application__learner_name="Arjun Demo").first()
        if arjun is not None:
            placement.place(admin, next_6a, [arjun.id])

    def _meridian_academics(self, actor) -> None:
        """Meridian College as a college: 2026–27 with two semesters, Physics and Mathematics, program BSC-PHY and its
        regulation R2026 — a synthetic regulation for development, not any real university's — published; semester 1
        offerings PHY101-A with its lab PHY101L-A1; meridian.faculty teaching PHY101-A and the batch BSC-PHY 2026 A;
        two students, one placed in the batch and one pinned to the program alone."""
        from academics import curricula, offerings, placement, programs, sections, structure
        from students.models import Enrollment, Person, Student

        meridian = Institution.objects.get(slug="meridian")
        admin = User.objects.get(username="meridian.admin")
        self._switch_on(meridian, admin, "academics", "admissions", "students")
        main = Campus.objects.get_or_create(institution=meridian, code="MAIN", defaults={"name": "Main campus"})[0]
        physics = Department.objects.get_or_create(
            institution=meridian, code="PHY", defaults={"name": "Physics", "campus": main}
        )[0]
        maths = Department.objects.get_or_create(
            institution=meridian, code="MATH", defaults={"name": "Mathematics", "campus": main}
        )[0]
        faculty = self._member(meridian, actor, "meridian.faculty", "Meridian Physics Faculty", "teacher", physics)
        if meridian.academic_years.exists():
            return
        year = structure.save_year(
            admin,
            meridian,
            None,
            {"code": "2026–27", "starts_on": dt.date(2026, 6, 1), "ends_on": dt.date(2027, 3, 31), "status": "current"},
        )
        semester_1 = structure.save_term(
            admin,
            year,
            None,
            {"name": "Semester 1", "ordinal": 1, "starts_on": dt.date(2026, 6, 1), "ends_on": dt.date(2026, 10, 31)},
        )
        structure.save_term(
            admin,
            year,
            None,
            {"name": "Semester 2", "ordinal": 2, "starts_on": dt.date(2026, 11, 1), "ends_on": dt.date(2027, 3, 31)},
        )
        program = programs.save_program(
            admin,
            meridian,
            None,
            {"code": "BSC-PHY", "name": "B.Sc Physics", "qualification": "B.Sc", "length_terms": 6,
             "department": physics.id},
        )  # fmt: skip
        courses = {
            code: programs.save_course(
                admin,
                meridian,
                None,
                {"code": code, "title": title, "credits": credits, "kind": kind, "department": department.id},
            )
            for code, title, credits, kind, department in (
                ("PHY101", "Mechanics", 4, "theory", physics),
                ("PHY101L", "Mechanics Lab", 1, "lab", physics),
                ("MAT101", "Calculus", 4, "theory", maths),
                ("PHY201", "Electromagnetism", 4, "theory", physics),
            )
        }
        regulation = curricula.create(admin, program, {"regulation": "R2026", "cohort": 2026, "credits_required": 120})
        for code, category, term, needs in (
            ("PHY101", "core", 1, []),
            ("PHY101L", "lab", 1, []),
            ("MAT101", "core", 1, []),
            ("PHY201", "core", 3, ["PHY101"]),
        ):
            regulation = curricula.add_course(
                admin,
                regulation,
                {"course": courses[code].id, "category": category, "term": term,
                 "prerequisites": [courses[n].id for n in needs]},
            )  # fmt: skip
        regulation = curricula.publish(admin, regulation, regulation.version)
        lecture = offerings.save_offering(
            admin,
            meridian,
            None,
            {"course": courses["PHY101"].id, "term": semester_1.id, "campus": main.id, "code": "A", "capacity": 60},
        )
        offerings.save_offering(
            admin,
            meridian,
            None,
            {"course": courses["PHY101L"].id, "term": semester_1.id, "campus": main.id, "code": "A1", "capacity": 30,
             "linked_to": lecture.id},
        )  # fmt: skip
        offerings.assign_teacher(admin, lecture, faculty.id)
        batch = sections.save_section(
            admin,
            meridian,
            None,
            {"year": year.id, "program": program.id, "campus": main.id, "code": "BSC-PHY 2026 A", "capacity": 60,
             "class_teacher": faculty.id},
        )  # fmt: skip
        made = []
        for name, curriculum in (("Ananya Demo", regulation), ("Rahul Demo", None)):
            person = Person.objects.create(institution=meridian, full_name=name)
            student = Student.objects.create(
                institution=meridian,
                person=person,
                number=Student.objects.next_number(meridian, 2026),
                admitted_on=dt.date(2026, 6, 1),
            )
            Enrollment.objects.create(
                student=student, institution=meridian, academic_year=year.code, place_code="BSC-PHY",
                place_label="B.Sc Physics", campus=main, entry_date=dt.date(2026, 6, 1), program=program,
                curriculum=curriculum,
            )  # fmt: skip
            made.append(student)
        placement.place(admin, batch, [made[0].id])

    def _meridian_registration(self, actor) -> None:
        """Semester 1's window (closed) with Ananya's results recorded, and Semester 2's open now with PHY201-A;
        `meridian.adviser`, and Ananya's own login `meridian.2026-0001`."""
        from academics import offerings, progress
        from academics.models import CourseAttempt, CourseRegistration, RegistrationWindow, Term
        from students.logins import make_login

        meridian = Institution.objects.get(slug="meridian")
        admin = User.objects.get(username="meridian.admin")
        self._switch_on(meridian, admin, "course_registration")
        self._member(meridian, actor, "meridian.adviser", "Meridian Academic Adviser", "academic_adviser", None)
        if RegistrationWindow.objects.filter(institution=meridian).exists():
            return
        first = Term.objects.get(year__institution=meridian, name="Semester 1")
        second = Term.objects.get(year__institution=meridian, name="Semester 2")
        main = meridian.campuses.get(code="MAIN")
        closed = RegistrationWindow.objects.create(
            institution=meridian, term=first, opens_on=dt.date(2026, 5, 15), closes_on=dt.date(2026, 6, 15),
            drop_until=dt.date(2026, 7, 1), max_credits=24,
        )  # fmt: skip
        today = today_for(meridian)
        RegistrationWindow.objects.create(
            institution=meridian, term=second, opens_on=today - dt.timedelta(days=9),
            closes_on=today + dt.timedelta(days=22), drop_until=today + dt.timedelta(days=37), max_credits=24,
        )  # fmt: skip
        courses = {c.code: c for c in meridian.courses.all()}
        maths = offerings.save_offering(
            admin, meridian, None,
            {"course": courses["MAT101"].id, "term": first.id, "campus": main.id, "code": "A", "capacity": 60},
        )  # fmt: skip
        semester_two = offerings.save_offering(
            admin, meridian, None,
            {"course": courses["PHY201"].id, "term": second.id, "campus": main.id, "code": "A", "capacity": 40},
        )  # fmt: skip
        for offering in (maths, semester_two):
            offerings.save_offering(admin, meridian, offering, {"status": "open"}, offering.version)
        lecture = meridian.offerings.get(course__code="PHY101", code="A")
        lab = meridian.offerings.get(course__code="PHY101L", code="A1")
        ananya = meridian.students.get(person__full_name="Ananya Demo")
        enrollment = ananya.enrollments.get()
        # Semester 1 happened before this demo begins: its registrations and results are written as they would stand.
        for offering, grade_point in ((lecture, 8), (lab, 9), (maths, 7)):
            registration = CourseRegistration.objects.create(
                institution=meridian, enrollment=enrollment, offering=offering, state="registered",
                curriculum=enrollment.curriculum, window=closed, window_version=closed.version, requested_by=admin,
            )  # fmt: skip
            attempt = CourseAttempt.objects.create(
                institution=meridian, enrollment=enrollment, course=offering.course, attempt_no=1,
                registration=registration, term=first, credits=offering.course.credits,
            )  # fmt: skip
            progress.record_outcome(admin, attempt, {"outcome": "passed", "grade_point": grade_point})
        ananya.user = make_login(admin, meridian, ananya.number, "Ananya Demo", PASSWORD)
        ananya.user.must_change_password = False
        ananya.user.last_login = timezone.now()
        ananya.user.save()
        ananya.save()

    def _affiliation(self, actor) -> None:
        """Summit University affiliates Meridian College: a grant approved by Meridian, and Meridian's Semester 1
        B.Sc Physics batch submitted for review."""
        from affiliations import services as affiliation
        from affiliations.models import AffiliationGrant

        meridian = Institution.objects.get(slug="meridian")
        summit = Institution.objects.get(slug="summit")
        # A college's plan doesn't include affiliations by default; Meridian bought it to send results to Summit.
        meridian.modules = sorted({*meridian.modules, "affiliations"})
        meridian.save(update_fields=["modules"])
        self._switch_on(summit, User.objects.get(username="summit.admin"), "academics", "exams", "affiliations")
        self._switch_on(meridian, User.objects.get(username="meridian.admin"), "exams", "affiliations")
        if AffiliationGrant.objects.filter(college=meridian, university=summit).exists():
            return
        admin = User.objects.get(username="meridian.admin")
        today = today_for(meridian)
        grant = affiliation.propose(
            actor,
            {"college": meridian, "university": summit, "purpose": "Central examination of B.Sc results (demo)",
             "starts_on": today - dt.timedelta(days=30), "ends_on": today + dt.timedelta(days=335),
             "evidence": "Synthetic affiliation order for development"},
        )  # fmt: skip
        grant = affiliation.approve(admin, grant, grant.version)
        term = meridian.academic_years.get(code="2026–27").terms.get(name="Semester 1")
        batch = affiliation.build(admin, grant, meridian.programs.get(code="BSC-PHY"), term)
        affiliation.submit(admin, batch)

    def _timetable(self) -> None:
        """Aster: Attendance on, room LAB-1, Term 1's timetable published (Science in 6A each weekday morning with
        aster.teacher), and a Science assignment for 6A."""
        from academics import timetable
        from academics.models import Room, Section, Subject, Term, TimetableVersion
        from attendance import services as attendance

        aster = Institution.objects.get(slug="aster")
        admin = User.objects.get(username="aster.admin")
        self._switch_on(aster, admin, "attendance")
        if Room.objects.filter(institution=aster).exists():
            return
        main = aster.campuses.get(code="MAIN")
        room = timetable.save_room(
            admin, aster, None, {"campus": main.id, "code": "LAB-1", "name": "Science lab", "capacity": 40}
        )
        term = Term.objects.get(year__institution=aster, year__code="2026–27", ordinal=1)
        section = Section.objects.get(institution=aster, year=term.year, code="6A")
        science = Subject.objects.get(institution=aster, code="SCI")
        teacher = Membership.objects.get(institution=aster, user__username="aster.teacher")
        draft = timetable.new_version(admin, term)
        for weekday in range(1, 6):
            timetable.add_slot(
                admin,
                draft,
                {"weekday": weekday, "starts_at": dt.time(9), "ends_at": dt.time(9, 45), "section": section.id,
                 "subject": science.id, "room": room.id, "teacher": teacher.id},
            )  # fmt: skip
        draft = TimetableVersion.objects.get(pk=draft.pk)
        timetable.publish(admin, draft, draft.version)
        attendance.post_assignment(
            teacher.user,
            aster,
            section,
            {"title": "Parts of a plant cell", "instructions": "Draw a plant cell and label five parts.",
             "due_at": timezone.now() + dt.timedelta(days=7)},
        )  # fmt: skip

    def _results(self, actor) -> None:
        """Assessment and results on at Aster (with report cards) and Meridian (outcomes are for engineering colleges);
        a published "Theory 40/60" scheme at each (synthetic bands); `meridian.exams`; Ananya's transcript issued."""
        from results import services as results
        from results.models import Scheme

        bands = [
            {"min": "90", "grade": "O", "point": "10"}, {"min": "75", "grade": "A", "point": "8"},
            {"min": "60", "grade": "B", "point": "7"}, {"min": "40", "grade": "C", "point": "5"},
            {"min": "0", "grade": "F", "point": "0"},
        ]  # fmt: skip
        components = [
            {"name": "Internal", "max_marks": 40, "weight": 40},
            {"name": "Final", "max_marks": 60, "weight": 60, "min_percent": 40},
        ]
        outcomes = Institution.objects.get(slug="meridian")  # outcome evidence isn't in a college plan by default
        outcomes.modules = sorted({*outcomes.modules, "outcomes"})
        outcomes.save(update_fields=["modules"])
        for slug, modules in (("aster", ("exams", "report_cards")), ("meridian", ("exams", "outcomes"))):
            institution = Institution.objects.get(slug=slug)
            admin = User.objects.get(username=f"{slug}.admin")
            self._switch_on(institution, admin, *modules)
            if Scheme.objects.filter(institution=institution).exists():
                continue
            draft = results.save_scheme(
                admin, institution, None, {"name": "Theory 40/60", "bands": bands, "components": components}
            )
            results.publish_scheme(admin, draft, draft.version)
        meridian = Institution.objects.get(slug="meridian")
        self._member(meridian, actor, "meridian.exams", "Meridian Examination Officer", "exam_officer", None)
        ananya = meridian.students.get(person__full_name="Ananya Demo")
        if not ananya.documents.exists():
            results.transcript(User.objects.get(username="meridian.exams"), ananya)

    def _fees(self, actor) -> None:
        """Fees on at Aster with `aster.accountant`; Arjun's account follows the pack's EX-01: a 10,000 tuition invoice,
        a 1,000 concession approved by the principal and 6,000 paid at the office, leaving 3,000 owed. Online payment
        is left unconfigured, so families see "pay at the office"."""
        from decimal import Decimal

        from fees import services as fees
        from fees.models import FeeHead

        aster = Institution.objects.get(slug="aster")
        self._switch_on(aster, User.objects.get(username="aster.admin"), "fees")
        accountant = self._member(aster, actor, "aster.accountant", "Aster Accountant", "accountant", None).user
        if FeeHead.objects.filter(institution=aster).exists():
            return
        tuition = fees.save_head(accountant, aster, {"code": "TUITION", "name": "Tuition"})
        fees.save_head(accountant, aster, {"code": "TRANSPORT", "name": "Transport"})
        arjun = aster.students.get(application__learner_name="Arjun Demo")
        invoice = fees.issue_invoice(
            accountant,
            arjun,
            {
                "due_on": dt.date(2026, 11, 15),
                "lines": [{"head": tuition.id, "amount": Decimal("10000.00"), "description": "Tuition 2027–28"}],
            },
        )
        note = fees.request_credit(
            accountant, invoice, {"kind": "concession", "amount": Decimal("1000.00"), "reason": "Sibling concession"}
        )
        fees.decide_credit(User.objects.get(username="aster.principal"), note, approve=True)
        fees.collect(accountant, arjun, {"amount": Decimal("6000.00"), "channel": "cash", "reference": "Counter 1"})

    def _communication(self) -> None:
        """Messages on at Aster; Arjun's parent also shares fees and messages; his Science teacher has written to them.
        No media provider is set up, so calls and online classes say so honestly."""
        from communication import services as comms
        from communication.models import Conversation

        aster = Institution.objects.get(slug="aster")
        self._switch_on(aster, User.objects.get(username="aster.admin"), "communication")
        arjun = aster.students.get(application__learner_name="Arjun Demo")
        arjun.guardian_links.filter(user__username="aster.parent").update(access_fees=True, access_messages=True)
        if Conversation.objects.filter(institution=aster).exists():
            return
        comms.start(
            User.objects.get(username="aster.teacher"),
            aster,
            {"student": arjun.id, "with": User.objects.get(username="aster.parent").id, "subject": "Settling in",
             "body": "Arjun has settled in well. He asked good questions in Science today.", "client_id": "seed-1"},
        )  # fmt: skip

    def _development(self, actor) -> None:
        """Cases at Aster (`aster.services` triage, `aster.grievance` officer): Arjun's confidential grievance, assigned
        with an internal and a visible note, and the teacher's certificate request waiting. At Meridian
        (`meridian.placement`, `meridian.research`, `meridian.iqac`): an internship Ananya is shortlisted for, Ananya
        as a research scholar under the physics faculty with a valid ethics approval, and a NAAC cycle asking the
        faculty for evidence."""
        from cases import services as cases
        from cases.models import ServiceCase
        from development import services as development
        from development.models import (
            Employer,
            EthicsApproval,
            EvidenceRequest,
            Milestone,
            Opportunity,
            ReviewCycle,
            Scholar,
            Supervision,
        )

        plans = (("aster", ("services", "reports")), ("meridian", ("placements", "quality", "reports")))
        for slug, extra in plans:
            institution = Institution.objects.get(slug=slug)
            institution.modules = sorted({*institution.modules, *extra})
            institution.save(update_fields=["modules"])
            self._switch_on(institution, User.objects.get(username=f"{slug}.admin"), *extra)
        aster, meridian = Institution.objects.get(slug="aster"), Institution.objects.get(slug="meridian")
        desk = self._member(aster, actor, "aster.services", "Aster Student Services", "student_services", None).user
        officer = self._member(aster, actor, "aster.grievance", "Aster Grievance Officer", "grievance_officer", None)
        placement = self._member(
            meridian, actor, "meridian.placement", "Meridian Placement Officer", "placement_officer", None
        )
        self._member(
            meridian, actor, "meridian.research", "Meridian Research Coordinator", "research_coordinator", None
        )
        self._member(meridian, actor, "meridian.iqac", "Meridian IQAC Coordinator", "iqac_coordinator", None)
        self._aster_employees()
        if not ServiceCase.objects.filter(institution=aster).exists():
            arjun = User.objects.get(username="aster.2027-0001")
            grievance = cases.open_case(
                arjun,
                aster,
                "grievance",
                "Science internal marks",
                "My science internal was entered as 12 out of 40; my answer sheet shows 22.",
            )
            grievance = cases.assign(desk, aster, grievance, officer)
            cases.add_note(officer.user, aster, grievance, "Asked the science department for the answer sheet.", True)
            cases.add_note(
                officer.user, aster, grievance, "We have asked for your answer sheet and will reply this week.", False
            )
            cases.open_case(
                User.objects.get(username="aster.teacher"),
                aster,
                "service_request",
                "Experience certificate",
                "Needed for a scholarship application by 15 November.",
            )
        if Employer.objects.filter(institution=meridian).exists():
            return
        ananya = meridian.students.get(person__full_name="Ananya Demo")
        employer = Employer.objects.create(
            institution=meridian, name="Tata Consultancy Services", contact="campus@tcs.example"
        )
        today = today_for(meridian)
        internship = Opportunity.objects.create(
            institution=meridian,
            employer=employer,
            kind="internship",
            title="Summer research intern",
            description="Eight weeks with the analytics team.",
            closes_on=today + dt.timedelta(days=21),
        )
        enrollment = ananya.enrollments.filter(status="active").first()
        if enrollment and enrollment.program_id:
            internship.programs.set([enrollment.program_id])
        applied = development.apply(ananya, internship, consent=True)
        development.office_move(placement.user, meridian, applied, "shortlisted")
        faculty = Membership.objects.get(institution=meridian, user__username="meridian.faculty")
        scholar = Scholar.objects.create(
            institution=meridian,
            student=ananya,
            topic="Thin-film solar cells from local materials",
            started_on=dt.date(2026, 7, 1),
        )
        Supervision.objects.create(scholar=scholar, supervisor=faculty, role="main", starts_on=dt.date(2026, 7, 1))
        EthicsApproval.objects.create(
            scholar=scholar,
            reference="MC/IEC/2026/04",
            committee="Meridian institutional ethics committee",
            valid_from=dt.date(2026, 7, 1),
            valid_to=dt.date(2027, 6, 30),
        )
        Milestone.objects.create(scholar=scholar, title="Literature review", due_on=today + dt.timedelta(days=30))
        Milestone.objects.create(
            scholar=scholar, title="Field measurements", due_on=today + dt.timedelta(days=120), needs_ethics=True
        )
        cycle = ReviewCycle.objects.create(institution=meridian, framework="NAAC", period="2025-26")
        EvidenceRequest.objects.create(
            cycle=cycle, criterion="3.2.1", title="Research papers per teacher, 2025-26", owner=faculty
        )

    def _staff_services(self, actor) -> None:
        """HR, payroll and stores at Aster (`aster.hr`, `aster.payroll`, `aster.stores`): leave types, the teacher's
        casual leave waiting for a decision, last month's payroll validated and waiting for the principal, a
        requisition over the single-approval limit with one of its two approvals, a stocked item, two bookable labs
        and a booking next week."""
        from hr import services as hr
        from hr.models import LeaveType
        from stores import services as stores
        from stores.models import Asset, Item, Supplier

        aster = Institution.objects.get(slug="aster")
        aster.modules = sorted({*aster.modules, "hr_payroll", "assets"})
        aster.save(update_fields=["modules"])
        admin = User.objects.get(username="aster.admin")
        self._switch_on(aster, admin, "hr_payroll", "assets")
        officer = self._member(aster, actor, "aster.hr", "Aster HR Officer", "hr_officer", None).user
        payroll = self._member(aster, actor, "aster.payroll", "Aster Payroll Officer", "payroll_officer", None).user
        keeper = self._member(aster, actor, "aster.stores", "Aster Store Keeper", "store_keeper", None).user
        self._aster_employees()
        if LeaveType.objects.filter(institution=aster).exists():
            return
        principal, teacher = (User.objects.get(username=f"aster.{name}") for name in ("principal", "teacher"))
        today = today_for(aster)
        casual, sick, unpaid = (
            hr.add_type(officer, aster, {"code": code, "name": name, "days_per_year": days, "paid": paid})
            for code, name, days, paid in (
                ("CL", "Casual leave", 12, True),
                ("SL", "Sick leave", 10, True),
                ("LWP", "Leave without pay", 30, False),
            )
        )
        soon = today + dt.timedelta(days=10)
        hr.request_leave(teacher, aster, casual, soon, soon + dt.timedelta(days=1), "Cousin's wedding")
        last_month = (today.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
        unpaid_day = last_month.replace(day=12)
        away = hr.request_leave(teacher, aster, unpaid, unpaid_day, unpaid_day, "Personal work")
        hr.decide(officer, aster, away, approve=True)
        sickness = hr.request_leave(officer, aster, sick, last_month.replace(day=5), last_month.replace(day=6), "Fever")
        hr.decide(principal, aster, sickness, approve=True)
        for username, gross, pf in (("teacher", "62000.00", "1800.00"), ("registrar", "54000.00", "1800.00")):
            employee = Membership.objects.get(institution=aster, user__username=f"aster.{username}").employee
            hr.set_pay(
                payroll,
                aster,
                employee,
                {"monthly_gross": gross, "deductions": {"pf": pf}, "effective_from": dt.date(2024, 6, 1)},
            )
        cycle = hr.prepare(payroll, aster, last_month)
        hr.validate(payroll, aster, cycle)
        stores.publish_rule(admin, aster, Decimal("50000.00"))
        microscope = Item.objects.create(institution=aster, code="MIC-01", name="Compound microscope")
        beakers = Item.objects.create(institution=aster, code="GLS-250", name="Beaker 250 ml", unit="box")
        supplier = Supplier.objects.create(institution=aster, name="Vijaya Lab Supplies", contact="040 2765 1100")
        big = stores.raise_requisition(
            keeper,
            aster,
            "Microscopes for the biology lab",
            [{"item": microscope.id, "quantity": "4", "unit_cost": "18500.00"}],
        )
        stores.decide(principal, aster, big, approve=True)
        small = stores.raise_requisition(
            keeper, aster, "Beakers for term 2", [{"item": beakers.id, "quantity": "6", "unit_cost": "450.00"}]
        )
        stores.decide(principal, aster, small, approve=True)
        stores.order(keeper, aster, small, supplier)
        stores.receive(keeper, aster, small, [{"line": small.lines.get().id, "quantity": "6"}])
        stores.move(keeper, aster, beakers, "issue", Decimal("2"), "Chemistry practical")
        for tag, name in (("LAB-PHY-1", "Physics lab"), ("LAB-CHE-1", "Chemistry lab")):
            stores.add_asset(
                keeper,
                aster,
                {"tag": tag, "name": name, "category": "Laboratory", "location": "Main block", "bookable": True},
            )
        projector = stores.add_asset(keeper, aster, {"tag": "PRJ-07", "name": "Epson projector", "category": "AV"})
        stores.maintenance(keeper, projector, "Lamp flickers")
        start = timezone.make_aware(dt.datetime.combine(today + dt.timedelta(days=7), dt.time(10, 0)))
        stores.book(
            teacher,
            Asset.objects.get(institution=aster, tag="LAB-PHY-1"),
            start,
            start + dt.timedelta(hours=2),
            "Class 9 optics practical",
        )

    def _campus(self, actor) -> None:
        """Library and transport at Aster (`aster.librarian`, `aster.transport`): two copies of a title, one lent to
        Arjun; a Lake Road route with Arjun on it and today's trip home. A hostel at Meridian (`meridian.warden`) with
        Ananya in residence. The modules are added to both plans, as the platform admin would."""
        from campus import hostel, library, transport
        from campus.models import Bed, Hostel, Title

        for slug, extra in (("aster", ("library", "transport")), ("meridian", ("hostel",))):
            institution = Institution.objects.get(slug=slug)
            institution.modules = sorted({*institution.modules, *extra})
            institution.save(update_fields=["modules"])
            self._switch_on(institution, User.objects.get(username=f"{slug}.admin"), *extra)
        aster, meridian = Institution.objects.get(slug="aster"), Institution.objects.get(slug="meridian")
        librarian = self._member(aster, actor, "aster.librarian", "Aster Librarian", "librarian", None).user
        office = self._member(aster, actor, "aster.transport", "Aster Transport Office", "transport_officer", None).user
        warden = self._member(meridian, actor, "meridian.warden", "Meridian Warden", "warden", None).user
        if Title.objects.filter(institution=aster).exists():
            return
        arjun = aster.students.get(application__learner_name="Arjun Demo")
        library.add_title(
            librarian, aster, {"title": "Wings of Fire", "author": "A. P. J. Abdul Kalam", "copies": ["WF-1", "WF-2"]}
        )
        library.issue(librarian, aster, "WF-1", student=arjun)
        van = transport.add_vehicle(office, aster, {"registration": "AP 16 AB 1234", "capacity": 30})
        stops = [{"name": "Lake Road", "time": "07:40"}, {"name": "Temple Street", "time": "07:55"}]
        route = transport.add_route(office, aster, {"name": "Lake Road", "vehicle": van, "stops": stops})
        today = today_for(aster)
        transport.assign(
            office, route, arjun, {"stop": "Lake Road", "starts_on": today, "ends_on": dt.date(2028, 3, 31)}
        )
        transport.plan_trip(
            office, route, {"date": today, "direction": "home", "driver": Membership.objects.get(user=office)}
        )
        block = Hostel.objects.create(institution=meridian, name="Meridian girls' hostel")
        for room, label in (("101", "A"), ("101", "B"), ("102", "A")):
            Bed.objects.create(hostel=block, room=room, label=label)
        ananya = meridian.students.get(person__full_name="Ananya Demo")
        place = hostel.request(
            warden, meridian, ananya, {"starts_on": dt.date(2026, 6, 1), "ends_on": dt.date(2027, 3, 31)}
        )
        place = hostel.approve(warden, place, block.beds.first())
        hostel.step(warden, place, "check-in")
