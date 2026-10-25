"""Reports and exports for institutions (institution/reports/), and health, alerts, jobs, backups and usage for the
platform (platform/…) — BUILD-11."""

from django.http import FileResponse
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import has_perm
from accounts.role_views import holds_any
from configuration.gates import require_module
from institutions.models import Institution
from operations import reports, services
from operations.models import Alert, BackupRecord, ExportJob, JobRun, RestoreDrill
from sites.permissions import PlatformAdmin


class ReportView(GenericAPIView):
    permission_classes = [IsAuthenticated, holds_any("institution.read")]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "reports")

    def report(self, key) -> reports.Report:
        found = reports.REPORTS.get(key)
        if found is None:
            raise NotFound()
        if not reports.may_run(self.request.user, self.request.institution, found):
            raise PermissionDenied("You can't run this report.")
        return found


class Reports(ReportView):
    def get(self, request):
        exports = has_perm(request.user, request.institution, services.EXPORT)
        return Response(
            [
                {"key": r.key, "title": r.title, "columns": list(r.columns), "can_export": exports}
                for r in reports.runnable(request.user, request.institution)
            ]
        )


class RunReport(ReportView):
    def get(self, request, key):
        return Response(reports.run(request.user, request.institution, self.report(key)))


class Exports(ReportView):
    def get(self, request):
        rows = ExportJob.objects.filter(institution=request.institution, requester=request.user)[:50]
        return Response([services.export_item(j) for j in rows])

    def post(self, request, key):
        job = services.request_export(request.user, request.institution, self.report(key))
        return Response(services.export_item(job), status=status.HTTP_202_ACCEPTED)


class ExportFile(ReportView):
    def get(self, request, pk):
        job = ExportJob.objects.filter(institution=request.institution, pk=pk).first()
        if job is None:
            raise NotFound()
        handle = services.download(request.user, request.institution, job)
        return FileResponse(handle, content_type="text/csv", as_attachment=True, filename=f"{job.report}.csv")


class PlatformView(GenericAPIView):
    permission_classes = [PlatformAdmin]


class Health(PlatformView):
    def get(self, request):
        tiles = services.health()
        return Response(
            {
                "tiles": tiles,
                "alerts": [services.alert_item(a) for a in Alert.objects.exclude(state=Alert.State.RESOLVED)],
            }
        )


class Alerts(PlatformView):
    def get(self, request):
        return Response([services.alert_item(a) for a in Alert.objects.select_related("owner")[:100]])


class Acknowledge(PlatformView):
    def post(self, request, pk):
        alert = Alert.objects.filter(pk=pk).first()
        if alert is None:
            raise NotFound()
        return Response(services.alert_item(services.acknowledge(request.user, alert)))


class Jobs(PlatformView):
    def get(self, request):
        return Response(
            [
                {
                    "task": r.task,
                    "status": r.status,
                    "detail": r.detail,
                    "started_at": r.started_at.isoformat(),
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                }
                for r in JobRun.objects.all()[:50]
            ]
        )


class Backups(PlatformView):
    def get(self, request):
        return Response(
            {
                "backups": [
                    {
                        "taken_at": b.taken_at.isoformat(),
                        "size_bytes": b.size_bytes,
                        "database_sha256": b.database_sha256,
                    }
                    for b in BackupRecord.objects.all()[:20]
                ],
                "drills": [
                    {"ran_at": d.ran_at.isoformat(), "seconds": str(d.seconds), "passed": d.passed, "detail": d.detail}
                    for d in RestoreDrill.objects.all()[:20]
                ],
            }
        )


class Usage(PlatformView):
    def get(self, request):
        return Response([services.usage(i) for i in Institution.objects.order_by("display_name")])
