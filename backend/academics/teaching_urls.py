"""A teacher's own classes, under teaching/ on an institution's own host."""

from django.urls import path

from academics import teaching

urlpatterns = [
    path("classes", teaching.Classes.as_view()),
    path("classes/<uuid:section>/students", teaching.ClassRoster.as_view()),
]
