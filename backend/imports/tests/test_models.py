import datetime as dt

import pytest
from django.db import IntegrityError, transaction

from imports.models import ImportedRecord, ImportJob
from students.models import Person, Student


def test_one_import_per_source_record(world):
    person = Person.objects.create(institution=world.a, full_name="Learner")
    student = Student.objects.create(
        institution=world.a, person=person, number="2026-0001", admitted_on=dt.date(2026, 6, 1)
    )
    job = ImportJob.objects.create(
        institution=world.a,
        source_system="Old ERP",
        file="imports/x.csv",
        original_name="x.csv",
        checksum="0" * 64,
        size=1,
    )

    def record(source_system="Old ERP", institution=world.a):
        return ImportedRecord.objects.create(
            institution=institution, source_system=source_system, entity_type="student", source_record_id="S-1",
            checksum="a" * 64, job=job, student=student,
        )  # fmt: skip

    record()
    record(source_system="Other ERP")
    record(institution=world.b)
    with pytest.raises(IntegrityError), transaction.atomic():
        record()
