"""Applicants' documents: private files (PDF, JPEG or PNG up to 5 MB, judged by their content), kept outside the public
media path and served only to their owner and the staff reviewing them (slice 4a S4-09)."""

import uuid

from django.db import transaction
from django.http import FileResponse
from rest_framework.exceptions import ValidationError

from admissions.applications import EDITABLE, wrong_stage
from admissions.models import Application, Document

MAX_BYTES = 5 * 1024 * 1024
SIGNATURES = (
    (b"%PDF-", "application/pdf", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
)


def sniff(upload) -> tuple[str, str]:
    """The real type of an upload from its first bytes, whatever its name says."""
    head = upload.read(16)
    upload.seek(0)
    for signature, content_type, extension in SIGNATURES:
        if head.startswith(signature):
            return content_type, extension
    raise ValidationError({"file": ["Upload a PDF, JPEG or PNG file."]})


def upload(actor, application: Application, code: str, file) -> Document:
    if file is None:
        raise ValidationError({"file": ["Choose a file to upload."]})
    if file.size > MAX_BYTES:
        raise ValidationError({"file": ["Files can be up to 5 MB."]})
    content_type, extension = sniff(file)
    requirement = application.cycle.documents.filter(code=code).first()
    if requirement is None:
        raise ValidationError({"requirement": ["This cycle does not ask for that document."]})
    with transaction.atomic():
        application = Application.objects.select_for_update().get(pk=application.pk)
        if application.stage not in EDITABLE:
            raise wrong_stage(application)
        application.documents.filter(requirement=requirement).exclude(status=Document.Status.REPLACED).update(
            status=Document.Status.REPLACED
        )
        document = Document(
            application=application,
            requirement=requirement,
            original_name=file.name[:200],
            content_type=content_type,
            size=file.size,
            uploaded_by=actor,
        )
        document.file.save(f"{uuid.uuid4()}.{extension}", file, save=False)
        document.save()
        application.save()  # a new document is a change to the application: its version moves on
        return document


def download_response(document: Document) -> FileResponse:
    response = FileResponse(
        document.file.open("rb"),
        content_type=document.content_type,
        as_attachment=True,
        filename=document.original_name,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
