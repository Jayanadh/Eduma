"""Settings, under institution/ on an institution's own host."""

from django.urls import path

from configuration import views

urlpatterns = [
    path("settings", views.SettingsList.as_view()),
    path("settings/<str:key>", views.SettingDetail.as_view()),
    path("settings/<str:key>/draft", views.Draft.as_view()),
    path("settings/<str:key>/draft/submit", views.Submit.as_view()),
    path("settings/<str:key>/draft/withdraw", views.Withdraw.as_view()),
    path("settings/<str:key>/revisions/<uuid:revision_id>/approve", views.Approve.as_view()),
    path("settings/<str:key>/revisions/<uuid:revision_id>/return", views.Return.as_view()),
    path("settings/<str:key>/revisions/<uuid:revision_id>/restore", views.Restore.as_view()),
]
