"""Demo data for a laptop: the platform admin and four made-up institutions, one per category, each with its own look.
Safe to run again: nothing is duplicated and the demo passwords are put back. Refuses to run with DEBUG off."""

import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from institutions import services
from institutions.models import Institution, LifecycleStatus
from sites import services as site_services

PASSWORD = "Demo-pass-2026"

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
                services.transition(institution.pk, platform_admin, to=LifecycleStatus.ACTIVE, reason="Demo data",
                                    version=institution.version)
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
