"""Procurement, stock, assets and lab booking (slice 10b S10B-06..09)."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Membership
from accounts.permissions import has_perm
from common import audit
from common.exceptions import Problem
from stores.models import (
    Approval,
    Asset,
    AssetEvent,
    Booking,
    Item,
    ProcurementRule,
    Requisition,
    RequisitionLine,
    StockMovement,
)

CENT = Decimal("0.01")
State = Requisition.State
SIGN = {"issue": -1, "return": 1, "adjust": 1}


def require(actor, institution, perm: str, message: str) -> None:
    if not has_perm(actor, institution, perm):
        raise PermissionDenied(message)


# Procurement (S10B-06, S10B-07)


def publish_rule(actor, institution, limit: Decimal) -> ProcurementRule:
    require(actor, institution, "procurement.approve", "Only approvers set the procurement rule.")
    last = ProcurementRule.objects.filter(institution=institution).first()
    made = ProcurementRule.objects.create(
        institution=institution, revision=(last.revision if last else 0) + 1, single_approval_limit=limit
    )
    audit.log(actor, "procurement_rule.published", made, f"Procurement rule revision {made.revision}")
    return made


def total(req: Requisition) -> Decimal:
    return sum((x.quantity * x.unit_cost for x in req.lines.all()), Decimal("0")).quantize(CENT)


def approvals_needed(req: Requisition) -> int:
    return 1 if total(req) <= req.rule.single_approval_limit else 2


def raise_requisition(actor, institution, title: str, lines: list[dict]) -> Requisition:
    require(actor, institution, "procurement.manage", "Only stores raises requisitions.")
    rule = ProcurementRule.objects.filter(institution=institution).first()
    if rule is None:
        raise Problem(409, "no_procurement_rule", "Publish the procurement rule first.")
    items = {str(i.id): i for i in Item.objects.filter(institution=institution, id__in=[x["item"] for x in lines])}
    if not lines or any(str(x["item"]) not in items for x in lines):
        raise ValidationError({"lines": ["Add at least one item from the item list."]})
    with transaction.atomic():
        req = Requisition.objects.create(institution=institution, title=title, rule=rule, requested_by=actor)
        RequisitionLine.objects.bulk_create(
            RequisitionLine(
                requisition=req, item=items[str(x["item"])], quantity=x["quantity"], unit_cost=x["unit_cost"]
            )
            for x in lines
        )
    audit.log(actor, "requisition.submitted", req, f"Requisition {title}")
    return req


def _locked(req: Requisition, *allowed: str) -> Requisition:
    req = Requisition.objects.select_for_update().select_related("rule").get(pk=req.pk)
    if req.state not in allowed:
        raise Problem(409, "invalid_transition", f"This requisition is {req.get_state_display().lower()}.")
    return req


def decide(actor, institution, req: Requisition, approve: bool) -> Requisition:
    require(actor, institution, "procurement.approve", "You can't approve requisitions.")
    if req.requested_by_id == actor.id:
        raise PermissionDenied("Someone other than who raised it decides a requisition.")
    with transaction.atomic():
        req = _locked(req, State.SUBMITTED)
        if not approve:
            req.state = State.REJECTED
        elif req.approvals.filter(approver=actor).exists():
            raise Problem(409, "already_approved", "You've approved this one; it needs a different approver.")
        else:
            Approval.objects.create(requisition=req, approver=actor)
            if req.approvals.count() >= approvals_needed(req):
                req.state = State.APPROVED
        req.save(update_fields=["state"])
    audit.log(actor, "requisition.approved" if approve else "requisition.rejected", req, req.title)
    return req


def order(actor, institution, req: Requisition, supplier) -> Requisition:
    require(actor, institution, "procurement.manage", "Only stores places orders.")
    with transaction.atomic():
        req = _locked(req, State.APPROVED)
        req.state, req.supplier = State.ORDERED, supplier
        req.save(update_fields=["state", "supplier"])
    audit.log(actor, "requisition.ordered", req, f"Ordered from {supplier.name}")
    return req


def receive(actor, institution, req: Requisition, rows: list[dict]) -> Requisition:
    """Never more than was ordered; what arrives goes into stock in the same transaction."""
    require(actor, institution, "procurement.manage", "Only stores receives goods.")
    with transaction.atomic():
        req = _locked(req, State.ORDERED, State.PARTIAL)
        lines = {str(x.id): x for x in req.lines.select_for_update().select_related("item")}
        for row in rows:
            line, quantity = lines.get(str(row["line"])), Decimal(str(row["quantity"]))
            if line is None or quantity <= 0:
                raise ValidationError({"lines": ["Give a quantity for a line of this requisition."]})
            if line.received + quantity > line.quantity:
                left = line.quantity - line.received
                raise ValidationError({"lines": [f"Only {left} {line.item.name} still to come."]})
            line.received += quantity
            line.save(update_fields=["received"])
            StockMovement.objects.create(
                item=line.item, quantity=quantity, kind="receive", reference=req.title, moved_by=actor
            )
        req.state = State.RECEIVED if all(x.received == x.quantity for x in lines.values()) else State.PARTIAL
        req.save(update_fields=["state"])
    audit.log(actor, "requisition.received", req, f"Received goods for {req.title}")
    return req


def requisition_item(req: Requisition) -> dict:
    lines = list(req.lines.select_related("item"))
    return {
        "id": str(req.id),
        "title": req.title,
        "state": req.state,
        "total": str(total(req)),
        "rule_revision": req.rule.revision,
        "approvals_needed": approvals_needed(req),
        "approvals": [a.approver.full_name for a in req.approvals.select_related("approver")],
        "requested_by": req.requested_by.full_name,
        "supplier": req.supplier.name if req.supplier_id else None,
        "created_at": req.created_at.isoformat(),
        "lines": [
            {
                "id": str(x.id),
                "item": {"id": str(x.item_id), "code": x.item.code, "name": x.item.name, "unit": x.item.unit},
                "quantity": str(x.quantity),
                "unit_cost": str(x.unit_cost),
                "received": str(x.received),
            }
            for x in lines
        ],
    }


# Stock (S10B-07)


def on_hand(item: Item) -> Decimal:
    return (item.movements.aggregate(n=Sum("quantity"))["n"] or Decimal("0")).quantize(CENT)


def move(actor, institution, item: Item, kind: str, quantity: Decimal, reference: str) -> StockMovement:
    require(actor, institution, "procurement.manage", "Only stores moves stock.")
    if kind not in SIGN or quantity == 0 or (kind != "adjust" and quantity < 0):
        raise ValidationError({"quantity": ["Issue or return a positive amount; adjust by any amount but zero."]})
    if kind == "adjust" and not reference.strip():
        raise ValidationError({"reference": ["Say why the stock is adjusted."]})
    with transaction.atomic():
        item = Item.objects.select_for_update().get(pk=item.pk)
        delta, now = SIGN[kind] * quantity, on_hand(item)
        if now + delta < 0:
            raise Problem(409, "insufficient_stock", f"Only {now} {item.unit} of {item.name} in stock.")
        made = StockMovement.objects.create(item=item, quantity=delta, kind=kind, reference=reference, moved_by=actor)
    audit.log(actor, f"stock.{kind}", item, f"{kind.title()} {quantity} {item.name}", institution=institution)
    return made


# Assets (S10B-08)


def add_asset(actor, institution, data: dict) -> Asset:
    require(actor, institution, "assets.manage", "Only stores keeps the asset register.")
    if Asset.objects.filter(institution=institution, tag=data["tag"]).exists():
        raise ValidationError({"tag": ["That tag is on another asset."]})
    made = Asset.objects.create(institution=institution, **data)
    audit.log(actor, "asset.added", made, f"Added {made.tag} {made.name}")
    return made


def _event(actor, asset: Asset, kind: str, note: str, allowed=(Asset.Status.IN_USE, Asset.Status.MAINTENANCE), to=None):
    require(actor, asset.institution, "assets.manage", "Only stores changes assets.")
    with transaction.atomic():
        asset = Asset.objects.select_for_update().get(pk=asset.pk)
        if asset.status not in allowed:
            raise Problem(409, "invalid_transition", f"This asset is {asset.get_status_display().lower()}.")
        if to:
            asset.status = to
            asset.save(update_fields=["status"])
        AssetEvent.objects.create(asset=asset, kind=kind, note=note, by=actor)
    audit.log(actor, f"asset.{kind}", asset, f"{asset.tag}: {note}")
    return asset


def transfer(actor, asset: Asset, custodian: Membership, note: str) -> Asset:
    asset = _event(actor, asset, "transferred", f"To {custodian.user.full_name}. {note}".strip())
    Asset.objects.filter(pk=asset.pk).update(custodian=custodian, location=note or asset.location)
    asset.refresh_from_db()
    return asset


def maintenance(actor, asset: Asset, note: str) -> Asset:
    return _event(actor, asset, "maintenance", note, (Asset.Status.IN_USE,), Asset.Status.MAINTENANCE)


def back_in_use(actor, asset: Asset) -> Asset:
    return _event(actor, asset, "back_in_use", "Back in use", (Asset.Status.MAINTENANCE,), Asset.Status.IN_USE)


def dispose(actor, asset: Asset, reason: str) -> Asset:
    if not reason.strip():
        raise ValidationError({"reason": ["Give the reason and who authorised it."]})
    asset = _event(actor, asset, "disposed", reason, to=Asset.Status.DISPOSED)
    Asset.objects.filter(pk=asset.pk).update(disposal_reason=reason)
    asset.refresh_from_db()
    return asset


def asset_item(asset: Asset, events=False) -> dict:
    custodian = asset.custodian
    item = {
        "id": str(asset.id),
        "tag": asset.tag,
        "name": asset.name,
        "category": asset.category,
        "location": asset.location,
        "custodian": {"id": str(custodian.id), "name": custodian.user.full_name} if custodian else None,
        "bookable": asset.bookable,
        "status": asset.status,
        "disposal_reason": asset.disposal_reason,
    }
    if events:
        item["events"] = [
            {"kind": e.kind, "note": e.note, "by": e.by.full_name, "at": e.at.isoformat()}
            for e in asset.events.select_related("by").order_by("at")
        ]
    return item


# Lab booking (S10B-09)


def book(actor, asset: Asset, starts_at, ends_at, purpose: str) -> Booking:
    if not asset.bookable:
        raise ValidationError({"asset": ["This asset isn't booked."]})
    if ends_at <= starts_at:
        raise ValidationError({"ends_at": ["A booking ends after it starts."]})
    if starts_at < timezone.now():
        raise ValidationError({"starts_at": ["That time has passed."]})
    with transaction.atomic():
        asset = Asset.objects.select_for_update().get(pk=asset.pk)  # one booking at a time per asset
        if asset.status != Asset.Status.IN_USE:
            raise Problem(409, "asset_unavailable", f"{asset.name} is {asset.get_status_display().lower()}.")
        taken = Booking.objects.filter(asset=asset, canceled=False, starts_at__lt=ends_at, ends_at__gt=starts_at)
        if taken.exists():
            raise Problem(409, "booking_conflict", f"{asset.name} is already booked then.")
        return Booking.objects.create(
            asset=asset, starts_at=starts_at, ends_at=ends_at, purpose=purpose, booked_by=actor
        )


def cancel_booking(actor, booking: Booking) -> Booking:
    if booking.booked_by_id != actor.id:
        require(actor, booking.asset.institution, "assets.manage", "Only who booked it or stores cancels.")
    Booking.objects.filter(pk=booking.pk).update(canceled=True)
    booking.refresh_from_db()
    return booking


def booking_item(b: Booking, viewer) -> dict:
    return {
        "id": str(b.id),
        "asset": {"id": str(b.asset_id), "tag": b.asset.tag, "name": b.asset.name},
        "starts_at": b.starts_at.isoformat(),
        "ends_at": b.ends_at.isoformat(),
        "purpose": b.purpose,
        "booked_by": b.booked_by.full_name,
        "canceled": b.canceled,
        "mine": b.booked_by_id == viewer.id,
    }
