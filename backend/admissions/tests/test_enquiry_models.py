import pytest
from django.db import IntegrityError, transaction

from admissions.models import Enquiry


def make(institution, number):
    return Enquiry.objects.create(
        institution=institution, number=number, contact_name="Asha", phone="+91 90000 12345", source="website"
    )


def test_enquiry_numbers_run_per_institution_and_year(world):
    assert Enquiry.objects.next_number(world.a, 2026) == "E2026-0001"
    make(world.a, "E2026-0001")
    assert Enquiry.objects.next_number(world.a, 2026) == "E2026-0002"
    assert Enquiry.objects.next_number(world.b, 2026) == "E2026-0001"
    assert Enquiry.objects.next_number(world.a, 2027) == "E2027-0001"
    with pytest.raises(IntegrityError), transaction.atomic():
        make(world.a, "E2026-0001")
