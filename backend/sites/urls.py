"""The site-editing routes, included twice in config.urls: for platform admins under
platform/institutions/<id>/site/ and for an institution's members under institution/site/ on its own host."""

from django.urls import path

from sites.views import DraftView, PublishView, RestoreView, RevisionsView

site_patterns = [
    path("draft", DraftView.as_view()),
    path("draft/publish", PublishView.as_view()),
    path("revisions", RevisionsView.as_view()),
    path("revisions/<uuid:revision_id>/restore", RestoreView.as_view()),
]
