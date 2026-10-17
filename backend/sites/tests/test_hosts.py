import pytest

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
    assert institution_url("aster") == "http://aster.localhost:4201"
    assert platform_url() == "http://localhost:4201"
    settings.EDUMA_BASE_URL = "https://eduma.app"
    assert institution_url("aster") == "https://aster.eduma.app"
