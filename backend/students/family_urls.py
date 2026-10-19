"""A guardian's children, under family/ on an institution's own host."""

from django.urls import path

from students import family

urlpatterns = [
    path("children", family.Children.as_view()),
    path("children/<uuid:pk>", family.Child.as_view()),
]
