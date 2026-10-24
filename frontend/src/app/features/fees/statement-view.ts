import { Component, input } from '@angular/core';
import { FeeStatement } from '../../core/api/types';
import { date, dateTime } from '../../core/format';

const STATE: Record<string, string> = { issued: 'Due', partially_paid: 'Part paid', paid: 'Paid', cancelled: 'Cancelled' };

/** A fee statement: what is charged, credited, paid and still owed; money not yet applied shows as credit. */
@Component({
  selector: 'app-statement-view',
  template: `
    @let s = statement();
    <p><strong>₹{{ s.outstanding }}</strong> outstanding @if (s.unapplied !== '0.00') { <span class="muted small">· ₹{{ s.unapplied }} paid and not yet applied (credit)</span> }</p>
    <ul class="rows">
      @for (i of s.invoices; track i.id) {
        <li>
          <span><strong>{{ i.number }}</strong> <span class="muted small">due {{ date(i.due_on) }} · ₹{{ i.issued_charges }}{{ i.credit_notes !== '0.00' ? ' − ₹' + i.credit_notes + ' credit' : '' }} · paid ₹{{ i.net_allocated }}</span></span>
          <span class="small">{{ state[i.state] }} · ₹{{ i.outstanding }} owed</span>
        </li>
      } @empty {
        <li class="muted small">No invoices.</li>
      }
    </ul>
    @if (s.payments.length) {
      <h3 class="small">Payments</h3>
      <ul class="rows">
        @for (p of s.payments; track p.id) {
          <li>
            <span>₹{{ p.amount }} <span class="muted small">· {{ p.channel }} · {{ dateTime(p.created_at) }}{{ p.receipt ? ' · receipt ' + p.receipt.number : '' }}</span></span>
            <span class="small">{{ p.state === 'pending' ? 'Confirmation pending — shown here once the provider confirms' : p.state_label }}</span>
          </li>
        }
      </ul>
    }
  `,
  styles: `
    .rows {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 0 0 8px;
      padding: 0;
      list-style: none;

      li {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        gap: 8px;
      }
    }
  `,
})
export class StatementView {
  readonly statement = input.required<FeeStatement>();
  protected readonly date = date;
  protected readonly dateTime = dateTime;
  protected readonly state = STATE;
}
