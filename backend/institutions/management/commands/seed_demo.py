"""Demo data for a laptop: the platform admin and four made-up institutions, one per category, each with its own look,
and at Aster a second campus, departments and staff with different roles. Safe to run again: nothing is duplicated
and the demo passwords are put back. Refuses to run with DEBUG off."""

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
            person, _ = User.objects.get_or_create(
                username=username, defaults={"full_name": full_name, "created_by": actor}
            )
            person.set_password(PASSWORD)
            person.must_change_password = False
            person.last_login = person.last_login or timezone.now()
            person.save()
            membership, _ = Membership.objects.get_or_create(
                institution=aster, user=person, defaults={"created_by": actor}
            )
            if membership.assignments.exists():
                continue
            scope = scopes.get(scope_code)
            kind = "institution" if scope is None else "campus" if isinstance(scope, Campus) else "department"
            RoleAssignment.objects.create(
                membership=membership,
                institution=aster,
                role_key="" if role == front.name else role,
                custom_role=front if role == front.name else None,
                scope_type=kind,
                campus=scope if kind == "campus" else None,
                department=scope if kind == "department" else None,
                starts_on=today_for(aster),
                created_by=actor,
            )

    def _aster_settings(self) -> None:
        """Aster has switched on Admissions and Students, through the same steps an admin takes."""
        from accounts.permissions import today_for
        from configuration import services as settings_services

        aster = Institution.objects.get(slug="aster")
        if aster.settings.filter(key="modules.enabled").exists():
            return
        admin = User.objects.get(username="aster.admin")
        draft = settings_services.open_draft(aster, admin, "modules.enabled")
        draft = settings_services.save_draft(aster, admin, "modules.enabled", draft.version, ["admissions", "students"])
        settings_services.submit(aster, admin, "modules.enabled", draft.version, today_for(aster), "Demo data")
