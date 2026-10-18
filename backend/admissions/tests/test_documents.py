import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from admissions.models import Document

from .conftest import APPS, applicant
from .test_applicant import start

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), (200, 10, 10)).save(buffer, format="PNG")
    return buffer.getvalue()


def upload(client, application_id, code, name, content, kind="application/pdf"):
    file = SimpleUploadedFile(name, content, content_type=kind)
    return client.post(f"{APPS}/{application_id}/documents", {"requirement": code, "file": file}, format="multipart")


@pytest.fixture
def asha(world, cycle, client_for):
    return client_for(world.a.slug, applicant(world.a, "asha.parent"))


def test_pdf_and_png_are_accepted_and_replace_earlier_ones(world, cycle, asha):
    draft = start(asha, cycle).json()
    first = upload(asha, draft["id"], "BIRTH", "birth.pdf", PDF)
    assert first.status_code == 201, first.json()
    assert upload(asha, draft["id"], "PHOTO", "me.png", png(), "image/png").status_code == 201
    upload(asha, draft["id"], "BIRTH", "birth-2.pdf", PDF)
    statuses = sorted(Document.objects.filter(requirement__code="BIRTH").values_list("status", flat=True))
    assert statuses == ["pending", "replaced"]
    shown = asha.get(f"{APPS}/{draft['id']}").json()["documents"]
    assert sorted(d["original_name"] for d in shown) == ["birth-2.pdf", "me.png"]


def test_content_not_the_name_decides(world, cycle, asha):
    draft = start(asha, cycle).json()
    fake = upload(asha, draft["id"], "BIRTH", "birth.pdf", b"just some text pretending")
    assert fake.status_code == 422 and fake.json()["errors"][0]["field"] == "file"
    big = upload(asha, draft["id"], "BIRTH", "big.pdf", PDF + b"0" * (5 * 1024 * 1024))
    assert big.status_code == 422


def test_only_this_cycles_requirements(world, cycle, asha):
    """Review Focus 3."""
    draft = start(asha, cycle).json()
    response = upload(asha, draft["id"], "PASSPORT", "p.pdf", PDF)
    assert response.status_code == 422 and response.json()["errors"][0]["field"] == "requirement"


def test_downloads_are_private_to_the_owner(world, cycle, asha, client_for):
    draft = start(asha, cycle).json()
    doc = upload(asha, draft["id"], "BIRTH", "birth.pdf", PDF).json()["documents"][0]
    url = f"{APPS}/{draft['id']}/documents/{doc['id']}"
    mine = asha.get(url)
    assert mine.status_code == 200 and b"".join(mine.streaming_content).startswith(b"%PDF")
    assert mine["Cache-Control"] == "private, no-store"
    assert mine["X-Content-Type-Options"] == "nosniff"
    assert mine["Content-Disposition"].startswith("attachment")
    other = client_for(world.a.slug, applicant(world.a, "ravi.parent"))
    assert other.get(url).status_code == 404


def test_upload_only_while_editable(world, cycle, asha):
    from admissions.models import Application

    draft = start(asha, cycle).json()
    Application.objects.filter(pk=draft["id"]).update(stage="submitted")
    refused = upload(asha, draft["id"], "BIRTH", "birth.pdf", PDF)
    assert refused.status_code == 409
