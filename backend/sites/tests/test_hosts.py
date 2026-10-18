import pytest
from rest_framework.test import APIClient

from institutions.models import Institution
from sites.hosts import institution_url, platform_url, resolve


@pytest.mark.parametrize(
    "host,expected",
    [
        ("eduma.test", ("platform", None)),
        ("eduma.test:4201", ("platform", None)),
        ("EDUMA.test", ("platform", None)),
        ("aster.eduma.test", ("institution", "aster")),
        ("Aster.EDUMA.test:80", ("institution", "aster")),
        ("aster-school.eduma.test", ("institution", "aster-school")),
        ("a.b.eduma.test", ("unknown", None)),
        ("www.eduma.test", ("unknown", None)),
        ("-x-.eduma.test", ("unknown", None)),
        ("evil.com", ("unknown", None)),
        ("noteduma.test", ("unknown", None)),
    ],
)
def test_resolve(host, expected):
    assert resolve(host) == expected


def test_urls_follow_the_base_url(settings):
    settings.EDUMA_BASE_URL = "http://localhost:4201"
    aster = Institution(slug="aster")
    assert institution_url(aster) == "http://aster.localhost:4201"
    assert platform_url() == "http://localhost:4201"
    settings.EDUMA_BASE_URL = "https://eduma.app"
    assert institution_url(aster) == "https://aster.eduma.app"
    aster.custom_domain = "www.aster.edu.in"
    assert institution_url(aster) == "https://www.aster.edu.in"


def test_custom_domain_serves_its_institution(world, settings):
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, "www.aster.edu.in", "www.nobody.edu.in"]
    Institution.objects.filter(pk=world.a.pk).update(custom_domain="www.aster.edu.in")
    body = APIClient(HTTP_HOST="WWW.Aster.edu.in:443").get("/api/v1/public/site").json()
    assert body["kind"] == "institution" and body["institution"]["display_name"] == "Aster School"
    assert APIClient(HTTP_HOST="aster.eduma.test").get("/api/v1/public/site").json()["kind"] == "institution"
    assert APIClient(HTTP_HOST="www.nobody.edu.in").get("/api/v1/public/site").status_code == 404
