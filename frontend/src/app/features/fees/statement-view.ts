import { Component, input } from '@angular/core';
import { FeeStatement } from '../../core/api/types';
import { date, dateTime, money } from '../../core/format';
import { StatusBadge } from '../../ui/status-badge';

const STATE: Record<string, string> = { issued: 'Due', partially_paid: 'Part paid', paid: 'Paid', cancelled: 'Cancelled' };

/** A fee statement: what is charged, credited, paid and still owed; money not yet applied shows as credit. */
@Component({
  selector: 'app-statement-view',
  imports: [StatusBadge],
  template: `
    @let s = statement();
    <div class="owed" [class.clear]="s.outstanding === '0.00'">
      <span class="label">{{ s.outstanding === '0.00' ? 'Nothing outstanding' : 'Outstanding' }}</span>
      <strong class="amount">{{ money(s.outstanding) }}</strong>
      @if (s.unapplied !== '0.00') { <span class="small">{{ money(s.unapplied) }} paid and not yet applied (credit)</span> }
    </div>
    <ul class="rows">
      @for (i of s.invoices; track i.id) {
        <li>
          <span><strong>{{ i.number }}</strong><span class="muted small meta">due {{ date(i.due_on) }} · {{ money(i.issued_charges) }}{{ i.credit_notes !== '0.00' ? ' − ' + money(i.credit_notes) + ' credit' : '' }} · paid {{ money(i.net_allocated) }}</span></span>
          <span class="small"><app-status-badge [status]="i.state" [label]="state[i.state]" /> {{ money(i.outstanding) }} owed</span>
        </li>
      } @empty {
        <li class="muted small">No invoices.</li>
      }
    </ul>
    @if (s.payments.length) {
      <h3 class="small payments">Payments</h3>
      <ul class="rows">
        @for (p of s.payments; track p.id) {
          <li>
            <span>{{ money(p.amount) }} <span class="muted small meta">{{ p.channel }} · {{ dateTime(p.created_at) }}{{ p.receipt ? ' · receipt ' + p.receipt.number : '' }}</span></span>
            <span class="small">
              <app-status-badge [status]="p.state" [label]="p.state === 'pending' ? 'Confirmation pending' : p.state_label" />
            </span>
          </li>
        }
      </ul>
    }
  `,
  styles: `
    .owed {
      display: flex;
      flex-direction: column;
      gap: 2px;
      margin-bottom: 12px;
      padding: 16px 18px;
      border: 2px solid var(--ink);
      border-radius: var(--radius-md);
      background: var(--brand-secondary-soft);
      box-shadow: var(--shadow-hard-sm);
    }

    .owed.clear {
      background: var(--success-soft);
    }

    .label {
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    .amount {
      font-family: var(--font-heading);
      font-size: clamp(28px, 8vw, 36px);
      line-height: 1.1;
    }

    .payments {
      margin: 16px 0 8px;
    }
  `,
})
export class StatementView {
  protected readonly money = money;
  readonly statement = input.required<FeeStatement>();
  protected readonly date = date;
  protected readonly dateTime = dateTime;
  protected readonly state = STATE;
}
