import { Component, computed, inject, input, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { FeeHeadT, FeePlanT, FeeStatement, StudentRecord } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { money } from '../../core/format';
import { load } from '../../core/load';
import { ToastService } from '../../ui/toast';
import { StatementView } from './statement-view';

/** A student's fees on their record (S8-02..05): invoices, payments at the office, credit notes and refunds asked for
 * here and approved by someone else. */
@Component({
  selector: 'app-fees-section',
  imports: [StatementView],
  template: `
    <section class="card stack">
      <h2 class="card-title">Fees</h2>
      @if (data.value(); as s) {
        <app-statement-view [statement]="s" />
        @if (can('fees.manage')) {
          <form id="issue-invoice" class="row" (submit)="$event.preventDefault(); invoice($any($event.target))">
            <div class="field"><label for="inv-plan">Invoice from</label>
              <select id="inv-plan">
                @for (p of published(); track p.id) { <option [value]="p.id">{{ p.name }} (rev {{ p.revision }})</option> }
                <option value="">A single charge…</option>
              </select></div>
            <div class="field"><label for="inv-head">Head</label>
              <select id="inv-head">@for (h of heads.value() ?? []; track h.id) { <option [value]="h.id">{{ h.code }} · {{ h.name }}</option> }</select></div>
            <div class="field"><label for="inv-amount">Amount (single charge)</label><input id="inv-amount" type="number" min="0" step="0.01" /></div>
            <div class="field"><label for="inv-due">Due</label><input id="inv-due" type="date" /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Issue invoice</button>
          </form>
        }
        @if (can('fees.collect')) {
          <form id="record-payment" class="row" (submit)="$event.preventDefault(); pay($any($event.target))">
            <div class="field"><label for="pay-amount">Received ₹</label><input id="pay-amount" type="number" min="0" step="0.01" /></div>
            <div class="field"><label for="pay-channel">By</label>
              <select id="pay-channel"><option value="cash">Cash</option><option value="cheque">Cheque</option><option value="bank_transfer">Bank transfer</option></select></div>
            <div class="field"><label for="pay-ref">Reference</label><input id="pay-ref" /></div>
            <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Record payment</button>
          </form>
        }
        @if (can('fees.manage') && s.invoices.length) {
          <form id="credit-note" class="row" (submit)="$event.preventDefault(); credit($any($event.target))">
            <div class="field"><label for="cn-invoice">Credit note on</label>
              <select id="cn-invoice">@for (i of s.invoices; track i.id) { <option [value]="i.id">{{ i.number }}</option> }</select></div>
            <div class="field"><label for="cn-kind">Kind</label>
              <select id="cn-kind"><option value="concession">Concession</option><option value="cancellation">Cancellation</option></select></div>
            <div class="field"><label for="cn-amount">₹</label><input id="cn-amount" type="number" min="0" step="0.01" /></div>
            <div class="field grow"><label for="cn-reason">Reason</label><input id="cn-reason" /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Ask for approval</button>
          </form>
        }
        @if (can('fees.collect')) {
          @for (p of s.payments; track p.id) {
            @if (p.state === 'succeeded') {
              <form class="row" [id]="'refund-' + p.id" (submit)="$event.preventDefault(); refund(p.id, $any($event.target))">
                <span class="small">Refund from {{ p.receipt?.number }} ({{ money(p.amount) }})</span>
                <label class="sr-only" [for]="'refund-amount-' + p.id">Amount</label><input [id]="'refund-amount-' + p.id" type="number" min="0" step="0.01" placeholder="₹" />
                <label class="sr-only" [for]="'refund-reason-' + p.id">Reason</label><input [id]="'refund-reason-' + p.id" placeholder="Reason" />
                <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Ask for refund</button>
              </form>
              @for (r of p.refunds; track r.id) {
                @if (r.state === 'approved') {
                  <p class="small">Refund {{ money(r.amount) }} approved — <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Mark refund ' + r.amount + ' returned'" (click)="complete(r.id)">Money returned</button></p>
                }
              }
            }
          }
        }
        @if (message(); as m) { <p class="field-error" role="alert">{{ m }}</p> }
      }
    </section>
  `,
  styles: `
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: end;
    }

    .grow {
      flex: 1 1 160px;
    }
  `,
})
export class FeesSection {
  protected readonly money = money;
  readonly student = input.required<StudentRecord>();
  private readonly api = inject(Api);
  private readonly auth = inject(AuthStore);
  private readonly toasts = inject(ToastService);
  protected readonly data = load(
    () => this.api.get<FeeStatement>(`institution/fees/students/${this.student().id}/statement`),
    () => this.student().id,
  );
  protected readonly heads = load(() => this.api.get<FeeHeadT[]>('institution/fees/heads'));
  private readonly plans = load(() => this.api.get<FeePlanT[]>('institution/fees/plans'));
  protected readonly published = computed(() => (this.plans.value() ?? []).filter((p) => p.status === 'published'));
  protected readonly busy = signal(false);
  protected readonly message = signal('');

  protected can(perm: string): boolean {
    return this.auth.can(perm);
  }

  private run(request: Observable<unknown>, done: string): void {
    this.busy.set(true);
    this.message.set('');
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        this.data.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.message.set(apiErrorMessage(err));
      },
    });
  }

  private field(form: HTMLFormElement, id: string): string {
    return form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
  }

  protected invoice(form: HTMLFormElement): void {
    const plan = this.field(form, 'inv-plan');
    const body = plan
      ? { plan }
      : { due_on: this.field(form, 'inv-due'), lines: [{ head: this.field(form, 'inv-head'), amount: this.field(form, 'inv-amount') }] };
    this.run(this.api.post(`institution/fees/students/${this.student().id}/invoices`, body), 'Invoice issued.');
  }

  protected pay(form: HTMLFormElement): void {
    const body = {
      student: this.student().id,
      amount: this.field(form, 'pay-amount'),
      channel: this.field(form, 'pay-channel'),
      reference: this.field(form, 'pay-ref'),
    };
    this.run(this.api.post('institution/fees/payments', body), 'Payment recorded; receipt issued.');
  }

  protected credit(form: HTMLFormElement): void {
    const body = {
      invoice: this.field(form, 'cn-invoice'),
      kind: this.field(form, 'cn-kind'),
      amount: this.field(form, 'cn-amount'),
      reason: this.field(form, 'cn-reason'),
    };
    this.run(this.api.post('institution/fees/credit-notes', body), 'Credit note sent for approval.');
  }

  protected refund(payment: string, form: HTMLFormElement): void {
    const body = { payment, amount: this.field(form, `refund-amount-${payment}`), reason: this.field(form, `refund-reason-${payment}`) };
    this.run(this.api.post('institution/fees/refunds', body), 'Refund sent for approval.');
  }

  protected complete(refund: string): void {
    this.run(this.api.post(`institution/fees/refunds/${refund}/complete`, {}), 'Refund recorded as returned.');
  }
}
