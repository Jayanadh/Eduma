"""Academic structure, under institution/academics/ on an institution's own host."""

from django.urls import path

from academics import he_views, views

urlpatterns = [
    path("years", views.YearList.as_view()),
    path("years/<uuid:pk>", views.YearDetail.as_view()),
    path("years/<uuid:pk>/terms", views.TermList.as_view()),
    path("terms/<uuid:pk>", views.TermDetail.as_view()),
    path("grades", views.GradeList.as_view()),
    path("grades/<uuid:pk>", views.GradeDetail.as_view()),
    path("subjects", views.SubjectList.as_view()),
    path("subjects/<uuid:pk>", views.SubjectDetail.as_view()),
    path("staff", views.StaffChoices.as_view()),
    path("sections", views.SectionList.as_view()),
    path("sections/<uuid:pk>", views.SectionDetail.as_view()),
    path("sections/<uuid:pk>/teachers", views.Teachers.as_view()),
    path("sections/<uuid:pk>/students", views.Roster.as_view()),
    path("sections/<uuid:pk>/move-up/preview", views.MoveUpPreview.as_view()),
    path("sections/<uuid:pk>/move-up", views.MoveUp.as_view()),
    path("sections/<uuid:pk>/students/<uuid:student>", views.Placement.as_view()),
    path("sections/<uuid:pk>/students/<uuid:student>/move", views.Move.as_view()),
    path("sections/<uuid:pk>/teachers/<uuid:assignment>/end", views.EndTeaching.as_view()),
    path("programs", he_views.ProgramList.as_view()),
    path("programs/<uuid:pk>", he_views.ProgramDetail.as_view()),
    path("courses", he_views.CourseList.as_view()),
    path("courses/<uuid:pk>", he_views.CourseDetail.as_view()),
]
