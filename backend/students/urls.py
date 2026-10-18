"""Students, under institution/ on an institution's own host."""

from django.urls import path

from students import views

urlpatterns = [
    path("students", views.StudentList.as_view()),
    path("students/<uuid:pk>", views.StudentDetail.as_view()),
]
