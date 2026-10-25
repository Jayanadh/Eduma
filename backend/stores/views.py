"""Procurement, stock, assets and lab booking under institution/stores/ (slice 10b)."""

from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.views import valid
from accounts.models import Membership
from accounts.permissions import has_perm
from accounts.role_views import holds_any
from configuration.gates import require_module
from stores import services
from stores.models import Asset, Booking, Item, ProcurementRule, Requisition, Supplier

Money = {"max_digits": 12, "decimal_places": 2}


def _found(queryset, pk):
    row = queryset.filter(pk=pk).first()
    if row is None:
        raise NotFound()
    return row


class StoresView(GenericAPIView):
    permission_classes = [IsAuthenticated, holds_any("institution.read")]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "assets")

    def needs(self, *perms):
        if not any(has_perm(self.request.user, self.request.institution, p) for p in perms):
            raise PermissionDenied("You can't see purchasing.")

    def mine(self, model, pk):
        return _found(model.objects.filter(institution=self.request.institution), pk)


class Rules(StoresView):
    def get(self, request):
        self.needs("procurement.manage", "procurement.approve")
        rows = ProcurementRule.objects.filter(institution=request.institution)
        return Response(
            [{"revision": r.revision, "single_approval_limit": str(r.single_approval_limit),
              "published_at": r.published_at.isoformat()} for r in rows]
        )  # fmt: skip

    def post(self, request):
        limit = serializers.DecimalField(min_value=0, **Money).to_internal_value(
            request.data.get("single_approval_limit")
        )
        made = services.publish_rule(request.user, request.institution, limit)
        return Response({"revision": made.revision}, status=status.HTTP_201_CREATED)


class Suppliers(StoresView):
    def get(self, request):
        self.needs("procurement.manage", "procurement.approve")
        rows = Supplier.objects.filter(institution=request.institution).order_by("name")
        return Response([{"id": str(x.id), "name": x.name, "contact": x.contact} for x in rows])

    def post(self, request):
        self.needs("procurement.manage")
        name = serializers.CharField(max_length=120).to_internal_value(request.data.get("name", ""))
        made = Supplier.objects.create(
            institution=request.institution, name=name.strip(), contact=str(request.data.get("contact", ""))[:120]
        )
        return Response({"id": str(made.id), "name": made.name}, status=status.HTTP_201_CREATED)


class ItemInput(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=120)
    unit = serializers.CharField(max_length=20, default="each")


class Items(StoresView):
    def get(self, request):
        self.needs("procurement.manage", "procurement.approve")
        rows = Item.objects.filter(institution=request.institution).annotate(n=Sum("movements__quantity"))
        return Response(
            [{"id": str(i.id), "code": i.code, "name": i.name, "unit": i.unit,
              "on_hand": str((i.n or Decimal("0")).quantize(services.CENT))} for i in rows.order_by("code")]
        )  # fmt: skip

    def post(self, request):
        self.needs("procurement.manage")
        data = valid(ItemInput, request.data)
        if Item.objects.filter(institution=request.institution, code=data["code"]).exists():
            raise serializers.ValidationError({"code": ["That code is taken."]})
        made = Item.objects.create(institution=request.institution, **data)
        return Response({"id": str(made.id), "code": made.code, "name": made.name}, status=status.HTTP_201_CREATED)


class LineInput(serializers.Serializer):
    item = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    unit_cost = serializers.DecimalField(min_value=0, **Money)


class RequisitionInput(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    lines = LineInput(many=True)


class Requisitions(StoresView):
    def get(self, request):
        self.needs("procurement.manage", "procurement.approve")
        rows = Requisition.objects.filter(institution=request.institution).select_related(
            "rule", "supplier", "requested_by"
        )
        if state := request.query_params.get("state"):
            rows = rows.filter(state=state)
        return Response([services.requisition_item(r) for r in rows[:100]])

    def post(self, request):
        data = valid(RequisitionInput, request.data)
        made = services.raise_requisition(request.user, request.institution, data["title"], data["lines"])
        return Response(services.requisition_item(made), status=status.HTTP_201_CREATED)


class RequisitionAction(StoresView):
    action = "approve"

    def post(self, request, pk):
        req = self.mine(Requisition, pk)
        if self.action in ("approve", "reject"):
            done = services.decide(request.user, request.institution, req, self.action == "approve")
        elif self.action == "order":
            supplier = self.mine(Supplier, request.data.get("supplier"))
            done = services.order(request.user, request.institution, req, supplier)
        else:
            rows = request.data.get("lines")
            if not isinstance(rows, list) or not all(isinstance(x, dict) and "line" in x for x in rows):
                raise serializers.ValidationError({"lines": ["Give the lines received."]})
            for row in rows:
                row["quantity"] = serializers.DecimalField(max_digits=10, decimal_places=2).to_internal_value(
                    row.get("quantity")
                )
            done = services.receive(request.user, request.institution, req, rows)
        return Response(services.requisition_item(done))


class MoveInput(serializers.Serializer):
    item = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=list(services.SIGN))
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    reference = serializers.CharField(max_length=150, allow_blank=True, default="")


class Stock(StoresView):
    def post(self, request):
        data = valid(MoveInput, request.data)
        item = self.mine(Item, data["item"])
        services.move(request.user, request.institution, item, data["kind"], data["quantity"], data["reference"])
        return Response({"on_hand": str(services.on_hand(item))}, status=status.HTTP_201_CREATED)


class AssetInput(serializers.Serializer):
    tag = serializers.CharField(max_length=30)
    name = serializers.CharField(max_length=120)
    category = serializers.CharField(max_length=60, allow_blank=True, default="")
    location = serializers.CharField(max_length=80, allow_blank=True, default="")
    bookable = serializers.BooleanField(default=False)


class Assets(StoresView):
    def get(self, request):
        rows = Asset.objects.filter(institution=request.institution).select_related("custodian__user")
        if not has_perm(request.user, request.institution, "assets.manage"):
            rows = rows.filter(bookable=True, status=Asset.Status.IN_USE)  # others see only what they can book
        if len(q := request.query_params.get("search", "").strip()) >= 3:
            rows = rows.filter(name__icontains=q) | rows.filter(tag__icontains=q)
        return Response([services.asset_item(a) for a in rows.order_by("tag")[:300]])

    def post(self, request):
        made = services.add_asset(request.user, request.institution, valid(AssetInput, request.data))
        return Response(services.asset_item(made), status=status.HTTP_201_CREATED)


class AssetDetail(StoresView):
    def get(self, request, pk):
        self.needs("assets.manage")
        return Response(services.asset_item(self.mine(Asset, pk), events=True))


class AssetAction(StoresView):
    action = "maintenance"

    def post(self, request, pk):
        asset = self.mine(Asset, pk)
        note = str(request.data.get("note", "")).strip()[:150]
        if self.action == "transfer":
            custodian = Membership.objects.filter(
                institution=request.institution,
                kind=Membership.Kind.STAFF,
                status=Membership.Status.ACTIVE,
                user__username=str(request.data.get("username", "")).strip().lower(),
            ).first()
            if custodian is None:
                raise serializers.ValidationError({"username": ["No active staff member has that username."]})
            done = services.transfer(request.user, asset, custodian, note)
        elif self.action == "maintenance":
            if not note:
                raise serializers.ValidationError({"note": ["Say what's wrong."]})
            done = services.maintenance(request.user, asset, note)
        elif self.action == "back":
            done = services.back_in_use(request.user, asset)
        else:
            done = services.dispose(request.user, asset, str(request.data.get("reason", ""))[:200])
        return Response(services.asset_item(done, events=True))


class BookingInput(serializers.Serializer):
    asset = serializers.UUIDField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    purpose = serializers.CharField(max_length=150)


class Bookings(StoresView):
    def get(self, request):
        rows = Booking.objects.filter(asset__institution=request.institution, canceled=False).select_related(
            "asset", "booked_by"
        )
        if asset := request.query_params.get("asset"):
            rows = rows.filter(asset=self.mine(Asset, asset))
        rows = rows.filter(ends_at__gte=timezone.now())
        return Response([services.booking_item(b, request.user) for b in rows[:300]])

    def post(self, request):
        data = valid(BookingInput, request.data)
        asset = self.mine(Asset, data["asset"])
        made = services.book(request.user, asset, data["starts_at"], data["ends_at"], data["purpose"])
        return Response(services.booking_item(made, request.user), status=status.HTTP_201_CREATED)


class CancelBooking(StoresView):
    def post(self, request, pk):
        booking = _found(
            Booking.objects.filter(asset__institution=request.institution).select_related("asset", "booked_by"), pk
        )
        return Response(services.booking_item(services.cancel_booking(request.user, booking), request.user))
