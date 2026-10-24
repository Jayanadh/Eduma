"""Demo data for a laptop: the platform admin and four made-up institutions, one per category, each with its own look,
and at Aster a second campus, departments and staff with different roles. Safe to run again: nothing is duplicated
and the demo passwords are put back. Refuses to run with DEBUG off."""

import datetime as dt
import uuid

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
        staff = aster.memberships.filter(kind=Membership.Kind.STAFF).order_by("user__username")
        for number, membership in enumerate(staff, start=1):
            Employee.objects.get_or_create(
                institution=aster,
                membership=membership,
                defaults={"employee_number": f"AST-{number:03d}", "joined_on": dt.date(2024, 6, 1)},
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
