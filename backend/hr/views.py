"""Leave, staff attendance, pay and payroll under institution/hr/ (slice 10b)."""

from django.http import HttpResponse
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.views import valid
from accounts.models import Employee
from accounts.permissions import has_perm, today_for
from accounts.role_views import holds_any
from configuration.gates import require_module
from hr import services
from hr.models import LeaveRequest, LeaveType, PayrollCycle


def _found(queryset, pk):
    row = queryset.filter(pk=pk).first()
    if row is None:
        raise NotFound()
    return row


class HrView(GenericAPIView):
    permission_classes = [IsAuthenticated, holds_any("institution.read")]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_module(request.institution, "hr_payroll")

    def any_of(self, *perms):
        return any(has_perm(self.request.user, self.request.institution, p) for p in perms)

    def leave(self, pk) -> LeaveRequest:
        """Approvers and HR reach anyone's request; everyone else only their own."""
        rows = LeaveRequest.objects.filter(employee__institution=self.request.institution).select_related(
            "employee__membership__user", "leave_type", "decided_by"
        )
        if not self.any_of("hr.manage", "hr.leave_approve"):
            rows = rows.filter(employee__membership__user=self.request.user)
        return _found(rows, pk)


class TypeInput(serializers.Serializer):
    code = serializers.CharField(max_length=10)
    name = serializers.CharField(max_length=60)
    days_per_year = serializers.IntegerField(min_value=0, max_value=366)
    paid = serializers.BooleanField(default=True)


class LeaveTypes(HrView):
    def get(self, request):
        rows = LeaveType.objects.filter(institution=request.institution).order_by("code")
        return Response(
            [{"id": str(t.id), "code": t.code, "name": t.name, "days_per_year": t.days_per_year, "paid": t.paid}
             for t in rows]
        )  # fmt: skip

    def post(self, request):
        made = services.add_type(request.user, request.institution, valid(TypeInput, request.data))
        return Response({"id": str(made.id), "code": made.code, "name": made.name}, status=status.HTTP_201_CREATED)


class LeaveInput(serializers.Serializer):
    leave_type = serializers.UUIDField()
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    reason = serializers.CharField(max_length=300)


class Leave(HrView):
    def get(self, request):
        rows = LeaveRequest.objects.filter(employee__institution=request.institution).select_related(
            "employee__membership__user", "leave_type", "decided_by"
        )
        if request.query_params.get("all"):
            if not self.any_of("hr.manage", "hr.leave_approve"):
                raise PermissionDenied("Only HR and approvers see everyone's leave.")
            if state := request.query_params.get("state"):
                rows = rows.filter(state=state)
        else:
            rows = rows.filter(employee__membership__user=request.user)
        mine = services.employee_of(request.user, request.institution)
        year = today_for(request.institution).year
        return Response(
            {
                "requests": [services.leave_item(r) for r in rows[:300]],
                "balances": services.balances(mine, year) if mine else [],
            }
        )

    def post(self, request):
        data = valid(LeaveInput, request.data)
        kind = _found(LeaveType.objects.filter(institution=request.institution), data["leave_type"])
        made = services.request_leave(
            request.user, request.institution, kind, data["starts_on"], data["ends_on"], data["reason"]
        )
        return Response(services.leave_item(made), status=status.HTTP_201_CREATED)


class LeaveAction(HrView):
    action = "approve"

    def post(self, request, pk):
        leave = self.leave(pk)
        if self.action == "cancel":
            done = services.cancel(request.user, request.institution, leave)
        else:
            done = services.decide(request.user, request.institution, leave, self.action == "approve")
        return Response(services.leave_item(done))


class DayInput(serializers.Serializer):
    date = serializers.DateField()
    marks = serializers.ListField(child=serializers.DictField())


class Attendance(HrView):
    def get(self, request):
        if not self.any_of("hr.manage"):
            raise PermissionDenied("Only HR sees staff attendance.")
        date = serializers.DateField().to_internal_value(
            request.query_params.get("date") or today_for(request.institution).isoformat()
        )
        return Response(services.day_sheet(request.institution, date))

    def post(self, request):
        data = valid(DayInput, request.data)
        services.record_day(request.user, request.institution, data["date"], data["marks"])
        return Response(services.day_sheet(request.institution, data["date"]))


class Employees(HrView):
    def get(self, request):
        return Response(services.directory(request.user, request.institution))


class PayInput(serializers.Serializer):
    monthly_gross = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    components = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0), default=dict
    )
    deductions = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0), default=dict
    )
    effective_from = serializers.DateField()


class Pay(HrView):
    def employee(self, pk):
        return _found(Employee.objects.filter(institution=self.request.institution), pk)

    def get(self, request, pk):
        return Response(services.pay_history(request.user, request.institution, self.employee(pk)))

    def post(self, request, pk):
        employee = self.employee(pk)
        services.require(request.user, request.institution, "payroll.manage", "Only payroll sees or changes pay.")
        services.set_pay(request.user, request.institution, employee, valid(PayInput, request.data))
        return Response(
            services.pay_history(request.user, request.institution, employee), status=status.HTTP_201_CREATED
        )


class PayrollView(HrView):
    def cycles(self):
        if not self.any_of("payroll.manage", "payroll.approve"):
            raise PermissionDenied("Only payroll sees payroll.")
        return PayrollCycle.objects.filter(institution=self.request.institution).select_related(
            "prepared_by", "approved_by"
        )


class Payroll(PayrollView):
    def get(self, request):
        return Response([services.cycle_item(c) for c in self.cycles()[:36]])

    def post(self, request):
        month = serializers.DateField().to_internal_value(request.data.get("month") or "")
        made = services.prepare(request.user, request.institution, month)
        return Response(services.cycle_item(made, lines=True), status=status.HTTP_201_CREATED)


class PayrollDetail(PayrollView):
    def get(self, request, pk):
        return Response(services.cycle_item(_found(self.cycles(), pk), lines=True))


class PayrollAction(PayrollView):
    action = "validate"

    def get(self, request, pk):
        """The exported file, at payroll/<id>/export."""
        if self.action != "export":
            raise NotFound()
        cycle = _found(self.cycles(), pk)
        response = HttpResponse(services.export_file(request.user, request.institution, cycle), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="payroll-{cycle.month:%Y-%m}.csv"'
        return response

    def post(self, request, pk):
        cycle = _found(self.cycles(), pk)
        done = {"validate": services.validate, "approve": services.approve, "export": services.export}[self.action](
            request.user, request.institution, cycle
        )
        return Response(services.cycle_item(done, lines=True))
