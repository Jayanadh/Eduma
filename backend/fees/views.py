"""Fees for staff (institution/fees/), students (student/fees), guardians (family/children/<id>/fees) and the provider
webhook (webhooks/payments/<provider>/<institution>) — slice 8."""

import csv
import io
from decimal import Decimal

from django.http import HttpResponse
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from academics.registration_views import OwnView
from academics.views import valid
from accounts.role_views import holds_any
from configuration.gates import module_on, require_module
from fees import services
from fees.models import CreditNote, FeeHead, FeePlan, Invoice, JournalLine, Payment, ReconciliationCase, Refund
from institutions.models import Institution
from students.family import FamilyView

Money = {"max_digits": 12, "decimal_places": 2}


def _found(queryset, pk):
    row = queryset.filter(pk=pk).first()
    if row is None:
        raise NotFound()
    return row


class LineInput(serializers.Serializer):
    head = serializers.UUIDField()
    amount = serializers.DecimalField(min_value=Decimal("0.01"), **Money)
    description = serializers.CharField(max_length=150, required=False, allow_blank=True)


class PlanLineInput(serializers.Serializer):
    head = serializers.UUIDField()
    amount = serializers.DecimalField(min_value=Decimal("0.01"), **Money)
    due_on = serializers.DateField()


class FeesView(GenericAPIView):
    permission_classes = [
        IsAuthenticated,
        holds_any("fees.read", "fees.manage", "fees.collect", "fees.approve", "fees.reconcile"),
    ]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "fees")

    def student(self, pk):
        return _found(self.request.institution.students.select_related("person"), pk)

    def invoices(self):
        return Invoice.objects.filter(account__institution=self.request.institution).select_related(
            "account__student__person"
        )


class Heads(FeesView):
    def get(self, request):
        return Response(
            [
                {"id": str(h.id), "code": h.code, "name": h.name}
                for h in FeeHead.objects.filter(institution=request.institution)
            ]
        )

    def post(self, request):
        data = {
            "code": str(request.data.get("code", "")).strip().upper(),
            "name": str(request.data.get("name", "")).strip(),
        }
        if not data["code"] or not data["name"]:
            raise serializers.ValidationError({"code": ["Give a code and a name."]})
        head = services.save_head(request.user, request.institution, data)
        return Response({"id": str(head.id), "code": head.code, "name": head.name}, status=status.HTTP_201_CREATED)


def plan_item(p: FeePlan) -> dict:
    return {
        "id": str(p.id),
        "version": p.version,
        "name": p.name,
        "revision": p.revision,
        "status": p.status,
        "lines": p.lines,
    }


class Plans(FeesView):
    def get(self, request):
        return Response([plan_item(p) for p in FeePlan.objects.filter(institution=request.institution)])

    def post(self, request):
        data = {
            "name": str(request.data.get("name", "")).strip(),
            "lines": valid_many(PlanLineInput, request.data.get("lines", [])),
        }
        return Response(
            plan_item(services.save_plan(request.user, request.institution, data)), status=status.HTTP_201_CREATED
        )


def valid_many(serializer, items):
    found = serializer(data=items, many=True)
    found.is_valid(raise_exception=True)
    return [dict(x) for x in found.validated_data]


class PlanAction(FeesView):
    action = "publish"

    def post(self, request, pk):
        plan = _found(FeePlan.objects.filter(institution=request.institution), pk)
        if self.action == "publish":
            done = services.publish_plan(request.user, plan, int(request.data.get("version", 0)))
        else:
            done = services.revise_plan(request.user, plan)
        return Response(
            plan_item(done), status=status.HTTP_201_CREATED if self.action == "revise" else status.HTTP_200_OK
        )


class StudentInvoices(FeesView):
    def post(self, request, pk):
        student = self.student(pk)
        data = {"plan": request.data.get("plan"), "due_on": request.data.get("due_on")}
        if not data["plan"]:
            data["lines"] = valid_many(LineInput, request.data.get("lines", []))
        return Response(
            services.invoice_item(services.issue_invoice(request.user, student, data)), status=status.HTTP_201_CREATED
        )


class Statement(FeesView):
    def get(self, request, pk):
        return Response(services.statement(self.student(pk)))


class InvoiceDetail(FeesView):
    def get(self, request, pk):
        return Response(services.invoice_item(_found(self.invoices(), pk)))


class CreditInput(serializers.Serializer):
    invoice = serializers.UUIDField()
    kind = serializers.ChoiceField(["concession", "cancellation"])
    amount = serializers.DecimalField(**Money)
    reason = serializers.CharField(max_length=300)


class CreditNotes(FeesView):
    def get(self, request):
        rows = CreditNote.objects.filter(
            invoice__account__institution=request.institution, state="requested"
        ).select_related("invoice")
        return Response(
            [
                {
                    "id": str(n.id),
                    "invoice": n.invoice.number,
                    "kind": n.kind,
                    "amount": services.money(n.amount),
                    "reason": n.reason,
                }
                for n in rows
            ]
        )

    def post(self, request):
        data = valid(CreditInput, request.data)
        invoice = _found(self.invoices(), data.pop("invoice"))
        note = services.request_credit(request.user, invoice, data)
        return Response({"id": str(note.id), "state": note.state}, status=status.HTTP_201_CREATED)


class DecideCredit(FeesView):
    approve = True

    def post(self, request, pk):
        note = _found(CreditNote.objects.filter(invoice__account__institution=request.institution), pk)
        done = services.decide_credit(request.user, note, self.approve)
        return Response({"id": str(done.id), "state": done.state})


class AllocationInput(serializers.Serializer):
    invoice = serializers.UUIDField()
    amount = serializers.DecimalField(**Money)


class PaymentInput(serializers.Serializer):
    student = serializers.UUIDField()
    amount = serializers.DecimalField(**Money)
    channel = serializers.ChoiceField(["cash", "cheque", "bank_transfer"])
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    allocations = AllocationInput(many=True, required=False)


class Payments(FeesView):
    def post(self, request):
        data = valid(PaymentInput, request.data)
        payment = services.collect(request.user, self.student(data.pop("student")), data)
        return Response(services.payment_item(payment), status=status.HTTP_201_CREATED)


def _payments(institution):
    return Payment.objects.filter(account__institution=institution).select_related("account__student")


class RefundInput(serializers.Serializer):
    payment = serializers.UUIDField()
    amount = serializers.DecimalField(**Money)
    reason = serializers.CharField(max_length=300)


def refund_item(r: Refund, impact: dict | None = None) -> dict:
    item = {"id": str(r.id), "amount": services.money(r.amount), "reason": r.reason, "state": r.state}
    if impact is not None:
        item["impact"] = impact
    return item


class Refunds(FeesView):
    def get(self, request):
        rows = Refund.objects.filter(
            payment__account__institution=request.institution, state__in=("requested", "approved")
        )
        return Response([refund_item(r, services.impact(r)) for r in rows.select_related("payment")])

    def post(self, request):
        data = valid(RefundInput, request.data)
        payment = _found(_payments(request.institution), data["payment"])
        refund, impact = services.request_refund(request.user, payment, data["amount"], data["reason"])
        return Response(refund_item(refund, impact), status=status.HTTP_201_CREATED)


class RefundAction(FeesView):
    action = "approve"

    def post(self, request, pk):
        refund = _found(
            Refund.objects.filter(payment__account__institution=request.institution).select_related("payment__account"),
            pk,
        )
        if self.action == "approve":
            done = services.approve_refund(request.user, refund)
        elif self.action == "reject":
            done = services.reject_refund(request.user, refund)
        else:
            done = services.complete_refund(
                request.user, refund, str(request.data.get("reference", "")), failed=self.action == "fail"
            )
        return Response(refund_item(done))


class ProviderView(FeesView):
    def get(self, request):
        from fees.models import ProviderConfig

        found = ProviderConfig.objects.filter(institution=request.institution).first()
        return Response(
            {"provider": found.provider, "mode": found.mode, "merchant_id": found.merchant_id} if found else None
        )

    def put(self, request):
        data = {k: str(request.data.get(k, "")).strip() for k in ("provider", "merchant_id", "webhook_secret")}
        if not all(data.values()):
            raise serializers.ValidationError({"provider": ["Give the provider, merchant id and webhook secret."]})
        found = services.configure(request.user, request.institution, data)
        return Response({"provider": found.provider, "mode": found.mode, "merchant_id": found.merchant_id})


class Orders(FeesView):
    def post(self, request):
        invoice = _found(self.invoices(), request.data.get("invoice"))
        payment = services.create_order(invoice.account.student, invoice, request.user)
        return Response(services.payment_item(payment), status=status.HTTP_201_CREATED)


class SettlementInput(serializers.Serializer):
    provider = serializers.CharField(max_length=20)
    batch_ref = serializers.CharField(max_length=80)
    bank_ref = serializers.CharField(max_length=80)
    gross = serializers.DecimalField(**Money)
    fee = serializers.DecimalField(**Money)
    net = serializers.DecimalField(**Money)
    payments = serializers.ListField(child=serializers.UUIDField(), min_length=1)


class Settlements(FeesView):
    def post(self, request):
        made = services.settle(request.user, request.institution, valid(SettlementInput, request.data))
        return Response({"id": str(made.id), "batch_ref": made.batch_ref}, status=status.HTTP_201_CREATED)


class Cases(FeesView):
    def get(self, request):
        rows = ReconciliationCase.objects.filter(institution=request.institution, state="open").order_by("-opened_at")
        return Response(
            [
                {
                    "id": str(c.id),
                    "source": c.source,
                    "expected": services.money(c.expected) if c.expected is not None else None,
                    "observed": services.money(c.observed) if c.observed is not None else None,
                    "discrepancy": c.discrepancy,
                }
                for c in rows
            ]
        )


class Resolve(FeesView):
    def post(self, request, pk):
        case = _found(ReconciliationCase.objects.filter(institution=request.institution), pk)
        done = services.resolve(request.user, case, str(request.data.get("resolution", "")))
        return Response({"id": str(done.id), "state": done.state})


class TrialBalance(FeesView):
    def get(self, request):
        return Response(services.trial_balance(request.institution))


class JournalExport(FeesView):
    """The accounting boundary (S8-06): every posted line, for the institution's own books."""

    def get(self, request):
        services._require(request.user, request.institution, "fees.reconcile")
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["date", "posting_key", "memo", "account", "debit", "credit", "student", "invoice"])
        lines = JournalLine.objects.filter(journal__institution=request.institution).select_related(
            "journal", "student", "invoice"
        )
        for x in lines.order_by("journal__posted_at"):
            writer.writerow(
                [
                    x.journal.date,
                    x.journal.posting_key,
                    x.journal.memo,
                    x.account,
                    x.debit,
                    x.credit,
                    x.student.number if x.student_id else "",
                    x.invoice.number if x.invoice_id else "",
                ]
            )
        response = HttpResponse(out.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="fee-journal.csv"'
        return response


class Webhook(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, provider, institution):
        found = _found(Institution.objects.all(), institution)
        code, outcome = services.handle_event(
            found, provider, request.body, request.headers.get("X-Eduma-Signature", "")
        )
        return Response({"outcome": outcome}, status=code)


class OwnFees(OwnView):
    def get(self, request):
        require_module(request.institution, "fees")
        return Response(services.statement(self.me))


class OwnOrder(OwnView):
    def post(self, request):
        require_module(request.institution, "fees")
        invoice = _found(Invoice.objects.filter(account__student=self.me), request.data.get("invoice"))
        return Response(
            services.payment_item(services.create_order(self.me, invoice, request.user)), status=status.HTTP_201_CREATED
        )


class ChildFees(FamilyView):
    def child(self, pk):
        for student, shared in self.children().items():
            if student.pk == pk and shared and module_on(self.request.institution, "fees"):
                return student
        raise NotFound()

    def get(self, request, pk):
        return Response(services.statement(self.child(pk)))


class ChildOrder(ChildFees):
    def post(self, request, pk):
        student = self.child(pk)
        invoice = _found(Invoice.objects.filter(account__student=student), request.data.get("invoice"))
        return Response(
            services.payment_item(services.create_order(student, invoice, request.user)), status=status.HTTP_201_CREATED
        )
