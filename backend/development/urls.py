"""Placements, internships, alumni, research and quality evidence, under development/."""

from django.urls import path

from development import views

urlpatterns = [
    path("employers", views.Employers.as_view()),
    path("opportunities", views.Opportunities.as_view()),
    path("opportunities/<uuid:pk>/applications", views.Applications.as_view()),
    path("applications/<uuid:pk>/state", views.ApplicationMove.as_view()),
    path("placement-report", views.Report.as_view()),
    path("internships", views.Internships.as_view()),
    path("internships/<uuid:pk>/supervisor", views.InternshipAction.as_view(action="supervisor")),
    path("internships/<uuid:pk>/evaluate", views.InternshipAction.as_view(action="evaluate")),
    path("alumni", views.Alumni.as_view()),
    path("scholars", views.Scholars.as_view()),
    path("scholars/<uuid:pk>", views.ScholarDetail.as_view()),
    path("scholars/<uuid:pk>/supervisors", views.ScholarAction.as_view(action="supervisors")),
    path("scholars/<uuid:pk>/ethics", views.ScholarAction.as_view(action="ethics")),
    path("scholars/<uuid:pk>/milestones", views.ScholarAction.as_view(action="milestones")),
    path("supervisions/<uuid:pk>/end", views.EndSupervision.as_view()),
    path("milestones/<uuid:pk>/approve", views.MilestoneDecision.as_view(action="approve")),
    path("milestones/<uuid:pk>/return", views.MilestoneDecision.as_view(action="return")),
    path("cycles", views.Cycles.as_view()),
    path("cycles/<uuid:pk>", views.CycleDetail.as_view()),
    path("cycles/<uuid:pk>/requests", views.CycleAction.as_view(action="requests")),
    path("cycles/<uuid:pk>/freeze", views.CycleAction.as_view(action="freeze")),
    path("cycles/<uuid:pk>/export", views.CycleAction.as_view(action="export")),
    path("evidence", views.MyEvidence.as_view()),
    path("evidence/<uuid:pk>/upload", views.EvidenceAction.as_view(action="upload")),
    path("evidence/<uuid:pk>/accept", views.EvidenceAction.as_view(action="accept")),
    path("evidence/<uuid:pk>/return", views.EvidenceAction.as_view(action="return")),
    path("evidence-files/<uuid:pk>", views.EvidenceFile.as_view()),
]
