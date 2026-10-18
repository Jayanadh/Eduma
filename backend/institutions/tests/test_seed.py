import pytest
from django.core.management import CommandError, call_command

from accounts.models import User
from institutions.models import Institution
from sites.models import SiteRevision


def test_seed_runs_twice_without_duplicates(db, settings):
    settings.DEBUG = True
    call_command("seed_demo")
    User.objects.filter(username="aster.admin").update(full_name="Changed")
    call_command("seed_demo")
    assert Institution.objects.count() == 4
    assert User.objects.count() == 5
    assert SiteRevision.objects.filter(status="published").count() == 3
    states = dict(Institution.objects.values_list("slug", "lifecycle_status"))
    assert states == {"aster": "active", "meridian": "active", "vector": "setup", "summit": "active"}
    aster = SiteRevision.objects.get(institution__slug="aster", status="published")
    assert (aster.primary_color, aster.heading_font, aster.body_font) == ("#5B3FD9", "fredoka", "nunito")
    admin = User.objects.get(username="aster.admin")
    assert admin.check_password("Demo-pass-2026") and not admin.must_change_password
    vector = User.objects.get(username="vector.admin")
    assert vector.must_change_password and vector.last_login is None
    assert User.objects.get(username="eduma.admin").is_platform_admin
    assert Institution.objects.get(slug="meridian").custom_domain == "www.meridiancollege.localhost"


def test_seed_refuses_without_debug(db, settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_demo")
