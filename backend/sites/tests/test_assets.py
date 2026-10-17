import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from sites.models import BrandAsset

UPLOAD = "/api/v1/institution/site/assets"


def image_file(name="logo.png", fmt="PNG", size=(120, 80), exif=None) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    extra = {"exif": exif.tobytes()} if exif is not None else {}
    Image.new("RGB", size, (75, 90, 228)).save(buffer, format=fmt, **extra)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")


@pytest.fixture
def admin_a(world, client_for):
    return client_for(world.a.slug, world.a_admin)


def upload(client, file, url=UPLOAD):
    return client.post(url, {"file": file}, format="multipart")


def test_upload_png_records_size_and_hash(world, admin_a):
    response = upload(admin_a, image_file())
    assert response.status_code == 201
    body = response.json()
    assert body["url"] == f"/api/v1/public/assets/{body['id']}"
    assert (body["width"], body["height"]) == (120, 80)
    asset = BrandAsset.objects.get(pk=body["id"])
    assert asset.institution == world.a
    assert asset.content_type == "image/png"
    assert len(asset.sha256) == 64
    assert asset.file.name == f"brand/{world.a.id}/{asset.id}.png"


def test_upload_strips_exif(admin_a):
    exif = Image.Exif()
    exif[0x010F] = "Phone maker"
    exif[0x0110] = "Phone model"
    photo = image_file("photo.jpg", "JPEG", exif=exif)
    assert dict(Image.open(io.BytesIO(photo.read())).getexif())  # the upload really carries EXIF
    photo.seek(0)
    body = upload(admin_a, photo).json()
    with BrandAsset.objects.get(pk=body["id"]).file.open("rb") as stored:
        image = Image.open(stored)
        assert image.format == "JPEG"
        assert dict(image.getexif()) == {}


def test_platform_admin_uploads_for_any_institution(world, client_for):
    client = client_for(None, world.platform_admin)
    response = upload(client, image_file(), f"/api/v1/platform/institutions/{world.b.id}/site/assets")
    assert response.status_code == 201
    assert BrandAsset.objects.get(pk=response.json()["id"]).institution == world.b


@pytest.mark.parametrize(
    "file",
    [
        SimpleUploadedFile("logo.png", b"%PDF-1.7 not an image", content_type="image/png"),
        SimpleUploadedFile("empty.png", b"", content_type="image/png"),
        SimpleUploadedFile("big.png", b"\x89PNG\r\n\x1a\n" + b"\0" * (5 * 1024 * 1024 + 1), content_type="image/png"),
    ],
    ids=["disguised-pdf", "empty", "over-5mb"],
)
def test_rejects_bad_files(admin_a, file):
    response = upload(admin_a, file)
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "file"
    assert BrandAsset.objects.count() == 0


def test_rejects_too_many_pixels_and_other_formats(admin_a):
    assert upload(admin_a, image_file(size=(4001, 10))).status_code == 422
    assert upload(admin_a, image_file("anim.gif", "GIF")).status_code == 422
    assert BrandAsset.objects.count() == 0


def test_rejects_decompression_bomb(admin_a):
    # A tiny PNG whose header claims 30000 x 30000 pixels.
    buffer = io.BytesIO()
    Image.new("1", (30000, 30000)).save(buffer, format="PNG")
    response = upload(admin_a, SimpleUploadedFile("bomb.png", buffer.getvalue(), content_type="image/png"))
    assert response.status_code == 422
    assert BrandAsset.objects.count() == 0


def test_missing_file_is_422(admin_a):
    assert admin_a.post(UPLOAD, {}, format="multipart").status_code == 422


def test_asset_of_b_cannot_be_used_in_a_draft(world, client_for):
    b_asset = upload(client_for(world.b.slug, world.b_admin), image_file()).json()["id"]
    client = client_for(world.a.slug, world.a_admin)
    draft = client.get("/api/v1/institution/site/draft").json()
    body = {"version": draft["version"], **{k: draft["theme"][k] for k in
            ("primary_color", "secondary_color", "heading_font", "body_font")}, "content": draft["content"]}
    response = client.put("/api/v1/institution/site/draft", {**body, "logo": b_asset})
    assert response.status_code == 422 and response.json()["errors"][0]["field"] == "logo"
    content = draft["content"]
    content["sections"][0]["images"][0]["asset"] = b_asset
    response = client.put("/api/v1/institution/site/draft", {**body, "logo": None, "content": content})
    assert response.status_code == 422 and response.json()["errors"][0]["field"] == "content"
    content["sections"][0]["images"][0]["asset"] = None
    own = upload(client, image_file()).json()["id"]
    assert client.put("/api/v1/institution/site/draft", {**body, "logo": own}).status_code == 200
