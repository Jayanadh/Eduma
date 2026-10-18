"""The site-editing routes, under institution/site/ on an institution's own host: its own admins brand and publish its
page; the platform admin only onboards it."""

from django.urls import path

from sites.views import AssetsView, DraftView, PublishView, RestoreView, RevisionsView

site_patterns = [
    path("draft", DraftView.as_view()),
    path("draft/publish", PublishView.as_view()),
    path("revisions", RevisionsView.as_view()),
    path("revisions/<uuid:revision_id>/restore", RestoreView.as_view()),
    path("assets", AssetsView.as_view()),
]
