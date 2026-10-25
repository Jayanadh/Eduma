"""Reports and exports, under institution/reports/."""

from django.urls import path

from operations import views

urlpatterns = [
    path("", views.Reports.as_view()),
    path("exports", views.Exports.as_view()),
    path("exports/<uuid:pk>/file", views.ExportFile.as_view()),
    path("<slug:key>", views.RunReport.as_view()),
    path("<slug:key>/exports", views.RequestExport.as_view()),
]

platform_patterns = [
    path("health", views.Health.as_view()),
    path("alerts", views.Alerts.as_view()),
    path("alerts/<uuid:pk>/acknowledge", views.Acknowledge.as_view()),
    path("jobs", views.Jobs.as_view()),
    path("backups", views.Backups.as_view()),
    path("usage", views.Usage.as_view()),
]
