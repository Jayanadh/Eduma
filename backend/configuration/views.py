"""Settings on an institution's own host (slice 3 spec §5). Every change answers with the setting as it now stands."""

from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.role_views import holds_any
from common.pagination import Pages
from configuration import services
from configuration.registry import definition
from configuration.serializers import (
    KEYS,
    DraftInput,
    RestoreInput,
    ReturnInput,
    SubmitInput,
    VersionInput,
    detail,
    history_queryset,
    revision_item,
    summary,
)
from sites.permissions import member_with


class SettingsView(GenericAPIView):
    pagination_class = Pages
    perm = "configuration.edit"

    def get_permissions(self):
        if self.request.method == "GET":
            return [holds_any("configuration.edit", "configuration.publish")()]
        return [member_with(self.perm)()]

    def answer(self, key: str) -> Response:
        institution = self.request.institution
        definition(key)
        page = self.paginate_queryset(history_queryset(institution, key))
        history = {
            "count": self.paginator.page.paginator.count,
            "results": [revision_item(r, self.request.user) for r in page],
        }
        return Response(detail(institution, key, self.request.user, history))

    def data(self, serializer_class):
        found = serializer_class(data=self.request.data)
        found.is_valid(raise_exception=True)
        return found.validated_data


class SettingsList(SettingsView):
    def get(self, request):
        return Response([summary(request.institution, key, request.user) for key in KEYS])


class SettingDetail(SettingsView):
    def get(self, request, key):
        return self.answer(key)


class Draft(SettingsView):
    def post(self, request, key):
        services.open_draft(request.institution, request.user, key)
        return self.answer(key)

    def put(self, request, key):
        definition(key)
        values = self.data(DraftInput)
        services.save_draft(request.institution, request.user, key, values["version"], values["value"])
        return self.answer(key)


class Submit(SettingsView):
    def post(self, request, key):
        definition(key)
        values = self.data(SubmitInput)
        services.submit(
            request.institution, request.user, key, values["version"], values["effective_from"], values["reason"]
        )
        return self.answer(key)


class Withdraw(SettingsView):
    def post(self, request, key):
        definition(key)
        services.withdraw(request.institution, request.user, key, self.data(VersionInput)["version"])
        return self.answer(key)


class Approve(SettingsView):
    perm = "configuration.publish"

    def post(self, request, key, revision_id):
        definition(key)
        services.approve(request.institution, request.user, revision_id, self.data(VersionInput)["version"])
        return self.answer(key)


class Return(SettingsView):
    perm = "configuration.publish"

    def post(self, request, key, revision_id):
        definition(key)
        values = self.data(ReturnInput)
        services.return_to_draft(request.institution, request.user, revision_id, values["version"], values["note"])
        return self.answer(key)


class Restore(SettingsView):
    def post(self, request, key, revision_id):
        definition(key)
        values = self.data(RestoreInput)
        services.restore(request.institution, request.user, key, revision_id, values["version"])
        return self.answer(key)
