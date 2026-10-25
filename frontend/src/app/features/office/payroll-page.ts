import { Component, inject, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AuthStore } from '../../core/auth-store';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { OFFICE_STYLES } from './office-styles';

type StaffPay = { id: string; number: string; name: string; pay: string | null };
type Line = { employee: { id: string; number: string; name: string }; gross: string; unpaid_days: number; unpaid_deduction: string; deductions: string; net: string };
type Cycle = {
  id: string;
  month: string;
  state: 'prepared' | 'validated' | 'approved' | 'exported';
  prepared_by: string;
  approved_by: string | null;
  exported_at: string | null;
  people: number;
  net: string;
  lines?: Line[];
};

/**
 * The payroll boundary (S10B-04, S10B-05): pay is seen here only with payroll.manage; a cycle is prepared, validated,
 * approved by someone else, then exported as a file for the payroll or bank system. Eduma pays nobody.
 */
@Component({
  selector: 'app-payroll-page',
  imports: [PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Administration" title="Payroll" subtitle="Prepare, check, approve and export. Deductions are what you enter; the file is not proof of payment." />
      <section class="card stack section">
        <h2 class="card-title">Payroll by month</h2>
        @if (manager) {
          <form id="prepare" class="row" (submit)="$event.preventDefault(); prepare($any($event.target))">
            <div class="field"><label for="pay-month">Month</label><input id="pay-month" type="month" required /></div>
            <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Prepare</button>
          </form>
        }
        <ul class="rows">
          @for (c of cycles.value() ?? []; track c.id) {
            <li>
              <span><strong>{{ monthName(c.month) }}</strong> <span class="muted small">· {{ c.state }} · {{ c.people }} people · net {{ c.net }} · prepared by {{ c.prepared_by }}{{ c.approved_by ? ' · approved by ' + c.approved_by : '' }}{{ c.exported_at ? ' · exported ' + dateTime(c.exported_at) : '' }}</span></span>
              <span class="actions">
                <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Lines for ' + monthName(c.month)" (click)="open.set(c.id)">Lines</button>
                @if (manager && c.state === 'prepared') { <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Validate ' + monthName(c.month)" (click)="step(c, 'validate')">Validate</button> }
                @if (approver && c.state === 'validated') { <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve ' + monthName(c.month)" (click)="step(c, 'approve')">Approve</button> }
                @if (manager && c.state === 'approved') { <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Export ' + monthName(c.month)" (click)="step(c, 'export')">Export</button> }
                @if (manager && c.state === 'exported') { <a class="btn btn-secondary btn-sm" [href]="'/api/v1/institution/hr/payroll/' + c.id + '/export'" download>Download file</a> }
              </span>
            </li>
          } @empty {
            <li class="muted small">No payroll yet.</li>
          }
        </ul>
        @if (detail.value(); as d) {
          <h3 class="card-title">{{ monthName(d.month) }}</h3>
          <ul class="rows">
            @for (x of d.lines ?? []; track x.employee.id) {
              <li><span>{{ x.employee.name }} <span class="muted small">{{ x.employee.number }}</span></span><span class="small">gross {{ x.gross }}{{ x.unpaid_days ? ' − ' + x.unpaid_deduction + ' for ' + x.unpaid_days + (x.unpaid_days === 1 ? ' unpaid day' : ' unpaid days') : '' }} − {{ x.deductions }} deductions = <strong>{{ x.net }}</strong></span></li>
            }
          </ul>
        }
      </section>
      @if (manager) {
        <section class="card stack section">
          <h2 class="card-title">Pay</h2>
          <ul class="rows">
            @for (p of staff.value() ?? []; track p.id) {
              <li><span>{{ p.name }} <span class="muted small">{{ p.number }}</span></span><span class="small">{{ p.pay ? p.pay + ' a month' : 'not set' }}</span></li>
            }
          </ul>
          <form id="set-pay" class="row" (submit)="$event.preventDefault(); setPay($any($event.target))">
            <div class="field grow"><label for="pay-person">Staff member</label>
              <select id="pay-person">@for (p of staff.value() ?? []; track p.id) { <option [value]="p.id">{{ p.name }}</option> }</select></div>
            <div class="field"><label for="pay-gross">Monthly gross</label><input id="pay-gross" inputmode="decimal" required /></div>
            <div class="field"><label for="pay-pf">Provident fund</label><input id="pay-pf" inputmode="decimal" /></div>
            <div class="field"><label for="pay-tds">Tax deducted</label><input id="pay-tds" inputmode="decimal" /></div>
            <div class="field"><label for="pay-from">From</label><input id="pay-from" type="date" required /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Save pay</button>
          </form>
        </section>
      }
    </div>
  `,
  styles: [OFFICE_STYLES],
})
export class PayrollPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly auth = inject(AuthStore);
  protected readonly dateTime = dateTime;
  protected readonly manager = this.auth.can('payroll.manage');
  protected readonly approver = this.auth.can('payroll.approve');
  protected readonly open = signal('');
  protected readonly cycles = load(() => this.api.get<Cycle[]>('institution/hr/payroll'));
  protected readonly detail = load(
    () => (this.open() ? this.api.get<Cycle>(`institution/hr/payroll/${this.open()}`) : of(null)),
    () => this.open(),
  );
  protected readonly staff = load(() => (this.manager ? this.api.get<StaffPay[]>('institution/hr/employees') : of([])));
  protected readonly busy = signal(false);

  protected monthName(month: string): string {
    return new Date(`${month}T00:00:00`).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  }

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        this.cycles.reload();
        this.detail.reload();
        this.staff.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected prepare(form: HTMLFormElement): void {
    const month = form.querySelector<HTMLInputElement>('#pay-month')!.value;
    this.run(this.api.post<Cycle>('institution/hr/payroll', { month: `${month}-01` }), 'Payroll prepared.', () => form.reset());
  }

  protected step(c: Cycle, action: 'validate' | 'approve' | 'export'): void {
    const words = { validate: 'Validated.', approve: 'Approved.', export: 'Exported. Download the file for the payroll system.' };
    this.open.set(c.id);
    this.run(this.api.post(`institution/hr/payroll/${c.id}/${action}`, {}), words[action]);
  }

  protected setPay(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
    const deductions = Object.fromEntries((['pf', 'tds'] as const).filter((k) => field(`pay-${k}`)).map((k) => [k, field(`pay-${k}`)]));
    const body = { monthly_gross: field('pay-gross'), deductions, effective_from: field('pay-from') };
    this.run(this.api.post(`institution/hr/employees/${field('pay-person')}/compensation`, body), 'Pay saved.', () => form.reset());
  }
}
