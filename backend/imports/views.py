"""Data transfer for the Institution Admin: staged student imports (slice 4c §5)."""

from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from accounts.role_views import holds_any
from common.pagination import Pages
from configuration.gates import require_module
from imports import services
from imports.models import ImportJob, ImportRow


class UploadInput(serializers.Serializer):
    file = serializers.FileField(allow_empty_file=True)
    source_system = serializers.CharField(max_length=60)


class DecideInput(serializers.Serializer):
    decision = serializers.ChoiceField([ImportRow.Decision.CREATE, ImportRow.Decision.SKIP])


def job_item(job: ImportJob) -> dict:
    undecided = job.rows.filter(state=ImportRow.State.DUPLICATE, decision="").count()
    return {
        "id": str(job.id),
        "version": job.version,
        "source_system": job.source_system,
        "original_name": job.original_name,
        "status": job.status,
        "status_label": job.get_status_display(),
        "totals": job.totals,
        "undecided": undecided,
        "created_at": job.created_at,
        "created_by": job.created_by.full_name if job.created_by_id else None,
        "committed_at": job.committed_at,
    }


def row_item(row: ImportRow) -> dict:
    return {
        "id": str(row.id),
        "row_number": row.row_number,
        "source_record_id": row.source_record_id,
        "full_name": row.raw.get("full_name", ""),
        "state": row.state,
        "state_label": row.get_state_display(),
        "errors": row.errors,
        "duplicate_of": row.duplicate_of,
        "decision": row.decision,
        "student": {"id": str(row.student_id), "number": row.student.number} if row.student_id else None,
    }


class ImportView(GenericAPIView):
    permission_classes = [holds_any("data.import")]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "students")

    def job(self) -> ImportJob:
        found = ImportJob.objects.filter(institution=self.request.institution, pk=self.kwargs["pk"]).first()
        if found is None:
            raise NotFound()
        return found


class JobList(ImportView):
    pagination_class = Pages
    parser_classes = [MultiPartParser]

    def get(self, request):
        jobs = ImportJob.objects.filter(institution=request.institution).select_related("created_by")
        page = self.paginate_queryset(jobs)
        return self.get_paginated_response([job_item(job) for job in page])

    def post(self, request):
        data = UploadInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        job = services.upload(request.user, request.institution, values["file"], values["source_system"].strip())
        return Response(job_item(job), status=status.HTTP_201_CREATED)


class JobDetail(ImportView):
    def get(self, request, pk):
        return Response(job_item(self.job()))


class JobRows(ImportView):
    pagination_class = Pages

    def get(self, request, pk):
        rows = self.job().rows.select_related("student")
        if state := request.query_params.get("state"):
            rows = rows.filter(state=state)
        page = self.paginate_queryset(rows)
        return self.get_paginated_response([row_item(row) for row in page])


class Decide(ImportView):
    def post(self, request, pk, row):
        found = self.job().rows.filter(pk=row).first()
        if found is None:
            raise NotFound()
        data = DecideInput(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(row_item(services.decide(request.user, found, data.validated_data["decision"])))
