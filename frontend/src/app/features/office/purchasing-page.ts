import { Component, inject, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { StatusBadge } from '../../ui/status-badge';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AuthStore } from '../../core/auth-store';
import { money } from '../../core/format';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { OFFICE_STYLES } from './office-styles';

type Rule = { revision: number; single_approval_limit: string; published_at: string };
type StockItem = { id: string; code: string; name: string; unit: string; on_hand: string };
type SupplierT = { id: string; name: string; contact: string };
type ReqLine = { id: string; item: { id: string; code: string; name: string; unit: string }; quantity: string; unit_cost: string; received: string };
type Req = {
  id: string;
  title: string;
  state: string;
  total: string;
  rule_revision: number;
  approvals_needed: number;
  approvals: string[];
  requested_by: string;
  supplier: string | null;
  lines: ReqLine[];
};

/**
 * Purchasing and stores (S10B-06, S10B-07): each requisition keeps the rule revision it was raised under; above the
 * single-approval limit two different people approve; goods received never exceed the order; stock never goes below zero.
 */
@Component({
  selector: 'app-purchasing-page',
  imports: [PageHeader, StatusBadge],
  template: `
    <div class="page">
      <app-page-header eyebrow="Campus" title="Purchasing" subtitle="Requisitions, orders, goods received and stock." />
      <section class="card stack section">
        <h2 class="card-title">Approval rule</h2>
        @if (rules.value()?.[0]; as r) {
          <p class="small">Revision {{ r.revision }}: one approver up to {{ money(r.single_approval_limit) }}; above that, two different approvers.</p>
        } @else {
          <p class="muted small">No rule yet. Requisitions start once an approver publishes one.</p>
        }
        @if (approver) {
          <form id="rule" class="row" (submit)="$event.preventDefault(); publish($any($event.target))">
            <div class="field"><label for="rule-limit">Single-approval limit</label><input id="rule-limit" inputmode="decimal" required /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Publish a new revision</button>
          </form>
        }
      </section>
      <section class="card stack section">
        <h2 class="card-title">Requisitions</h2>
        <ul class="rows">
          @for (q of reqs.value() ?? []; track q.id) {
            <li>
              <span><strong>{{ q.title }}</strong><app-status-badge [status]="q.state" /><span class="muted small meta">{{ money(q.total) }} · {{ q.approvals.length }} of {{ q.approvals_needed }} approvals (rule {{ q.rule_revision }}) · by {{ q.requested_by }}{{ q.supplier ? ' · ' + q.supplier : '' }}</span></span>
              <span class="actions">
                @if (approver && q.state === 'submitted') {
                  <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve ' + q.title" (click)="act(q, 'approve')">Approve</button>
                  <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Reject ' + q.title" (click)="act(q, 'reject')">Reject</button>
                }
                @if (manager && q.state === 'approved') {
                  <label class="sr-only" [for]="'supplier-' + q.id">Supplier</label>
                  <select [id]="'supplier-' + q.id">@for (s of suppliers.value() ?? []; track s.id) { <option [value]="s.id">{{ s.name }}</option> }</select>
                  <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Order ' + q.title" (click)="order(q)">Order</button>
                }
                @if (manager && (q.state === 'ordered' || q.state === 'partially_received')) {
                  <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Receive the rest of ' + q.title" (click)="receive(q)">Receive the rest</button>
                }
              </span>
            </li>
          } @empty {
            <li class="muted small">No requisitions yet.</li>
          }
        </ul>
        @if (manager) {
          <form id="new-req" class="row" (submit)="$event.preventDefault(); raise($any($event.target))">
            <div class="field grow"><label for="req-title">What for</label><input id="req-title" maxlength="150" required /></div>
            <div class="field"><label for="req-item">Item</label>
              <select id="req-item">@for (i of items.value() ?? []; track i.id) { <option [value]="i.id">{{ i.name }}</option> }</select></div>
            <div class="field"><label for="req-qty">Quantity</label><input id="req-qty" inputmode="decimal" required /></div>
            <div class="field"><label for="req-cost">Unit cost</label><input id="req-cost" inputmode="decimal" required /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Raise requisition</button>
          </form>
        }
      </section>
      <section class="card stack section">
        <h2 class="card-title">Stock</h2>
        <ul class="rows">
          @for (i of items.value() ?? []; track i.id) {
            <li><span><strong>{{ i.code }}</strong> {{ i.name }}</span><span class="small">{{ i.on_hand }} {{ i.unit }}</span></li>
          } @empty {
            <li class="muted small">No items yet.</li>
          }
        </ul>
        @if (manager) {
          <form id="move" class="row" (submit)="$event.preventDefault(); move($any($event.target))">
            <div class="field"><label for="move-item">Item</label>
              <select id="move-item">@for (i of items.value() ?? []; track i.id) { <option [value]="i.id">{{ i.name }}</option> }</select></div>
            <div class="field"><label for="move-kind">Move</label>
              <select id="move-kind"><option value="issue">Issue</option><option value="return">Return</option><option value="adjust">Adjust (±)</option></select></div>
            <div class="field"><label for="move-qty">Quantity</label><input id="move-qty" inputmode="decimal" required /></div>
            <div class="field grow"><label for="move-ref">For / why</label><input id="move-ref" maxlength="150" /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Record</button>
          </form>
          <form id="add-item" class="row" (submit)="$event.preventDefault(); addItem($any($event.target))">
            <div class="field"><label for="item-code">Code</label><input id="item-code" maxlength="20" required /></div>
            <div class="field grow"><label for="item-name">Name</label><input id="item-name" maxlength="120" required /></div>
            <div class="field"><label for="item-unit">Unit</label><input id="item-unit" maxlength="20" value="each" /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add item</button>
          </form>
          <form id="add-supplier" class="row" (submit)="$event.preventDefault(); addSupplier($any($event.target))">
            <div class="field grow"><label for="supplier-name">Supplier</label><input id="supplier-name" maxlength="120" required /></div>
            <div class="field grow"><label for="supplier-contact">Contact</label><input id="supplier-contact" maxlength="120" /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add supplier</button>
          </form>
        }
      </section>
    </div>
  `,
  styles: [OFFICE_STYLES],
})
export class PurchasingPage {
  protected readonly money = money;
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly auth = inject(AuthStore);
  protected readonly manager = this.auth.can('procurement.manage');
  protected readonly approver = this.auth.can('procurement.approve');
  protected readonly rules = load(() => this.api.get<Rule[]>('institution/stores/rules'));
  protected readonly reqs = load(() => this.api.get<Req[]>('institution/stores/requisitions'));
  protected readonly items = load(() => this.api.get<StockItem[]>('institution/stores/items'));
  protected readonly suppliers = load(() => this.api.get<SupplierT[]>('institution/stores/suppliers'));
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        for (const list of [this.rules, this.reqs, this.items, this.suppliers]) {
          list.reload();
        }
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  private field(form: HTMLFormElement, id: string): string {
    return form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
  }

  protected publish(form: HTMLFormElement): void {
    this.run(this.api.post('institution/stores/rules', { single_approval_limit: this.field(form, 'rule-limit') }), 'Rule published.', () => form.reset());
  }

  protected act(q: Req, action: 'approve' | 'reject'): void {
    this.run(this.api.post(`institution/stores/requisitions/${q.id}/${action}`, {}), action === 'approve' ? 'Approved.' : 'Rejected.');
  }

  protected order(q: Req): void {
    const supplier = (document.getElementById(`supplier-${q.id}`) as HTMLSelectElement | null)?.value;
    this.run(this.api.post(`institution/stores/requisitions/${q.id}/order`, { supplier }), 'Ordered.');
  }

  protected receive(q: Req): void {
    const lines = q.lines
      .map((x) => ({ line: x.id, quantity: (Number(x.quantity) - Number(x.received)).toFixed(2) }))
      .filter((x) => Number(x.quantity) > 0);
    this.run(this.api.post(`institution/stores/requisitions/${q.id}/receive`, { lines }), 'Received into stock.');
  }

  protected raise(form: HTMLFormElement): void {
    const f = (id: string) => this.field(form, id);
    const body = { title: f('req-title'), lines: [{ item: f('req-item'), quantity: f('req-qty'), unit_cost: f('req-cost') }] };
    this.run(this.api.post('institution/stores/requisitions', body), 'Requisition raised.', () => form.reset());
  }

  protected move(form: HTMLFormElement): void {
    const f = (id: string) => this.field(form, id);
    const body = { item: f('move-item'), kind: f('move-kind'), quantity: f('move-qty'), reference: f('move-ref') };
    this.run(this.api.post('institution/stores/stock', body), 'Stock recorded.', () => form.reset());
  }

  protected addItem(form: HTMLFormElement): void {
    const f = (id: string) => this.field(form, id);
    this.run(this.api.post('institution/stores/items', { code: f('item-code'), name: f('item-name'), unit: f('item-unit') || 'each' }), 'Item added.', () => form.reset());
  }

  protected addSupplier(form: HTMLFormElement): void {
    const f = (id: string) => this.field(form, id);
    this.run(this.api.post('institution/stores/suppliers', { name: f('supplier-name'), contact: f('supplier-contact') }), 'Supplier added.', () => form.reset());
  }
}
