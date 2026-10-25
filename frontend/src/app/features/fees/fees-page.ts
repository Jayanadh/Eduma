import { Component, inject, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { money } from '../../core/format';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { FeeHeadT, FeePlanT } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

type Pending = { id: string; invoice?: string; kind?: string; amount: string; reason: string; impact?: { outstanding_after: string | null } };
type Case = { id: string; source: string; expected: string | null; observed: string | null; discrepancy: string };

/** The fees office (S8-01..08): approvals waiting, fee heads and plans, the payment provider, settlements,
 * reconciliation cases and the ledger's trial balance. */
@Component({
  selector: 'app-fees-page',
  imports: [PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Fees" title="Fees office" subtitle="Charges, credits, payments and refunds post to a balanced ledger; nothing is edited after posting." />
      @if (can('fees.approve')) {
        <section class="card stack section">
          <h2 class="card-title">Waiting for your approval</h2>
          @for (n of credits.value() ?? []; track n.id) {
            <p class="small">Credit note {{ money(n.amount) }} on {{ n.invoice }} ({{ n.kind }}): {{ n.reason }}
              <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve credit note on ' + n.invoice" (click)="act('credit-notes/' + n.id + '/approve', 'Credit note posted.')">Approve</button>
              <button type="button" class="btn btn-secondary btn-sm" (click)="act('credit-notes/' + n.id + '/reject', 'Rejected.')">Reject</button></p>
          }
          @for (r of refunds.value() ?? []; track r.id) {
            @if (r.state === 'requested') {
              <p class="small">Refund {{ money(r.amount) }}: {{ r.reason }} @if (r.impact?.outstanding_after) { <span class="muted">· leaves {{ money(r.impact?.outstanding_after) }} owed</span> }
                <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve refund ' + r.amount" (click)="act('refunds/' + r.id + '/approve', 'Refund approved.')">Approve</button>
                <button type="button" class="btn btn-secondary btn-sm" (click)="act('refunds/' + r.id + '/reject', 'Rejected.')">Reject</button></p>
            }
          }
          @if (!(credits.value()?.length) && !hasRequestedRefund()) { <p class="muted small">Nothing waiting.</p> }
        </section>
      }
      @if (can('fees.manage')) {
        <section class="card stack section">
          <h2 class="card-title">Fee heads and plans</h2>
          <p class="small">@for (h of heads.value() ?? []; track h.id) { <span class="part">{{ h.code }} {{ h.name }}</span> } @empty { <span class="muted">No fee heads.</span> }</p>
          <form id="add-head" class="row" (submit)="$event.preventDefault(); head($any($event.target))">
            <div class="field"><label for="head-code">Code</label><input id="head-code" /></div>
            <div class="field"><label for="head-name">Name</label><input id="head-name" /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add fee head</button>
          </form>
          <ul class="rows">
            @for (p of plans.value() ?? []; track p.id) {
              <li><span>{{ p.name }} <span class="muted small">rev {{ p.revision }} · {{ p.status }} · @for (l of p.lines; track $index) { {{ money(l.amount) }} by {{ l.due_on }} }</span></span>
                @if (p.status === 'draft') { <button type="button" class="btn btn-primary btn-sm" (click)="act('plans/' + p.id + '/publish', 'Plan published.', { version: p.version })">Publish</button> }
                @if (p.status === 'published') { <button type="button" class="btn btn-secondary btn-sm" (click)="act('plans/' + p.id + '/revise', 'Revision drafted.')">New revision</button> }
              </li>
            }
          </ul>
          <form id="add-plan" class="row" (submit)="$event.preventDefault(); plan($any($event.target))">
            <div class="field grow"><label for="plan-name">Plan</label><input id="plan-name" placeholder="Class 6 2026–27" /></div>
            <div class="field"><label for="plan-head">Head</label><select id="plan-head">@for (h of heads.value() ?? []; track h.id) { <option [value]="h.id">{{ h.code }}</option> }</select></div>
            <div class="field"><label for="plan-amount">₹</label><input id="plan-amount" type="number" min="0" step="0.01" /></div>
            <div class="field"><label for="plan-due">Due</label><input id="plan-due" type="date" /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Save draft plan</button>
          </form>
        </section>
      }
      @if (can('fees.reconcile')) {
        <section class="card stack section">
          <h2 class="card-title">Online payments</h2>
          @if (provider.value(); as p) {
            <p class="small">{{ p.provider }} in <strong>{{ p.mode }}</strong> mode · merchant {{ p.merchant_id }}. Test mode takes no real money.</p>
          } @else {
            <p class="small">Not set up: families pay at the office. A real provider is chosen with Eduma (decision D-12); the sandbox below is for testing only.</p>
          }
          <form id="provider" class="row" (submit)="$event.preventDefault(); configure($any($event.target))">
            <div class="field"><label for="prov-merchant">Sandbox merchant id</label><input id="prov-merchant" /></div>
            <div class="field"><label for="prov-secret">Webhook secret</label><input id="prov-secret" type="password" /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Use the test sandbox</button>
          </form>
        </section>
        <section class="card stack section">
          <h2 class="card-title">Reconciliation</h2>
          @for (c of cases.value() ?? []; track c.id) {
            <form class="row" [id]="'case-' + c.id" (submit)="$event.preventDefault(); resolve(c.id, $any($event.target))">
              <span class="small grow">{{ c.source }}: {{ c.discrepancy }}{{ c.expected ? ' (expected ' + money(c.expected) + ', saw ' + money(c.observed) + ')' : '' }}</span>
              <label class="sr-only" [for]="'case-res-' + c.id">Resolution</label><input [id]="'case-res-' + c.id" placeholder="How it was resolved" />
              <button type="submit" class="btn btn-secondary btn-sm">Resolve</button>
            </form>
          } @empty {
            <p class="muted small">No open cases.</p>
          }
          <h3 class="small">Trial balance</h3>
          <p class="small">@for (t of trial.value() ?? []; track t.account) { <span class="part">{{ t.account }} {{ t.balance }}</span> }</p>
          <a class="small" href="/api/v1/institution/fees/journal.csv">Export the journal (CSV)</a>
        </section>
      }
    </div>
  `,
  styles: `
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: end;
    }

    .grow {
      flex: 1 1 200px;
    }

    .part + .part::before {
      content: ' · ';
    }
  `,
})
export class FeesPage {
  protected readonly money = money;
  private readonly api = inject(Api);
  private readonly auth = inject(AuthStore);
  private readonly toasts = inject(ToastService);
  private gated<T>(perm: string, path: string, empty: T): () => Observable<T> {
    return () => (this.auth.can(perm) ? this.api.get<T>(path) : of(empty));
  }
  protected readonly credits = load(this.gated<Pending[]>('fees.approve', 'institution/fees/credit-notes', []));
  protected readonly refunds = load(this.gated<(Pending & { state: string })[]>('fees.approve', 'institution/fees/refunds', []));
  protected readonly heads = load(this.gated<FeeHeadT[]>('fees.manage', 'institution/fees/heads', []));
  protected readonly plans = load(this.gated<FeePlanT[]>('fees.manage', 'institution/fees/plans', []));
  protected readonly provider = load(
    this.gated<{ provider: string; mode: string; merchant_id: string } | null>('fees.reconcile', 'institution/fees/provider', null),
  );
  protected readonly cases = load(this.gated<Case[]>('fees.reconcile', 'institution/fees/cases', []));
  protected readonly trial = load(this.gated<{ account: string; balance: string }[]>('fees.reconcile', 'institution/fees/trial-balance', []));
  protected readonly busy = signal(false);

  protected can(perm: string): boolean {
    return this.auth.can(perm);
  }

  protected hasRequestedRefund(): boolean {
    return (this.refunds.value() ?? []).some((r) => r.state === 'requested');
  }

  private reloadAll(): void {
    for (const each of [this.credits, this.refunds, this.heads, this.plans, this.provider, this.cases, this.trial]) {
      each.reload();
    }
  }

  private send(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        this.reloadAll();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected act(path: string, done: string, body: object = {}): void {
    this.send(this.api.post(`institution/fees/${path}`, body), done);
  }

  private field(form: HTMLFormElement, id: string): string {
    return form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
  }

  protected head(form: HTMLFormElement): void {
    this.send(this.api.post('institution/fees/heads', { code: this.field(form, 'head-code'), name: this.field(form, 'head-name') }), 'Fee head added.', () => form.reset());
  }

  protected plan(form: HTMLFormElement): void {
    const body = {
      name: this.field(form, 'plan-name'),
      lines: [{ head: this.field(form, 'plan-head'), amount: this.field(form, 'plan-amount'), due_on: this.field(form, 'plan-due') }],
    };
    this.send(this.api.post('institution/fees/plans', body), 'Plan saved as a draft.', () => form.reset());
  }

  protected configure(form: HTMLFormElement): void {
    const body = { provider: 'sandbox', merchant_id: this.field(form, 'prov-merchant'), webhook_secret: this.field(form, 'prov-secret') };
    this.send(this.api.put('institution/fees/provider', body), 'Test sandbox set up.', () => form.reset());
  }

  protected resolve(id: string, form: HTMLFormElement): void {
    this.send(this.api.post(`institution/fees/cases/${id}/resolve`, { resolution: this.field(form, `case-res-${id}`) }), 'Resolved.');
  }
}
