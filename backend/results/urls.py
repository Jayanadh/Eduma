"""Results, under institution/results/."""

from django.urls import path

from results import views

urlpatterns = [
    path("schemes", views.Schemes.as_view()),
    path("schemes/<uuid:pk>", views.SchemeDetail.as_view()),
    path("schemes/<uuid:pk>/publish", views.PublishScheme.as_view()),
    path("schemes/<uuid:pk>/revise", views.ReviseScheme.as_view()),
    path("assessments", views.Assessments.as_view()),
    path("assessments/<uuid:pk>", views.AssessmentDetail.as_view()),
    path("assessments/<uuid:pk>/marks", views.SaveMarks.as_view()),
    path("assessments/<uuid:pk>/submit", views.Step.as_view(action="submit")),
    path("assessments/<uuid:pk>/moderate", views.Step.as_view(action="moderate")),
    path("assessments/<uuid:pk>/return", views.Step.as_view(action="return")),
    path("assessments/<uuid:pk>/publish", views.Step.as_view(action="publish")),
    path("assessments/<uuid:pk>/mappings", views.Mappings.as_view()),
    path("assessments/<uuid:pk>/attainment", views.Attainment.as_view()),
    path("candidates/<uuid:pk>/cases", views.Cases.as_view()),
    path("cases/<uuid:pk>/approve", views.DecideCase.as_view(approve=True)),
    path("cases/<uuid:pk>/reject", views.DecideCase.as_view(approve=False)),
    path("students/<uuid:pk>/documents", views.Documents.as_view()),
    path("students/<uuid:pk>/promotion", views.Promotion.as_view()),
    path("documents/<uuid:pk>/revoke", views.Revoke.as_view()),
    path("courses/<uuid:pk>/outcomes", views.Outcomes.as_view()),
    path("affiliation-awards", views.AffiliationAward.as_view()),
]
