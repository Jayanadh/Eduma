import { Component, inject, input, output, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { FeePayment, FeeStatement } from '../../core/api/types';
import { ToastService } from '../../ui/toast';
import { StatementView } from './statement-view';

/** A family's or student's statement with online payment where set up. A payment only shows as received once the
 * provider confirms it; until then it says confirmation pending (S8-04, S8-09). */
@Component({
  selector: 'app-pay-online',
  imports: [StatementView],
  template: `
    @let s = statement();
    <app-statement-view [statement]="s" />
    @if (s.online) {
      @for (i of s.invoices; track i.id) {
        @if (i.outstanding !== '0.00') {
          <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="pay(i.id)">Pay ₹{{ i.outstanding }} for {{ i.number }} online</button>
        }
      }
    } @else if (s.outstanding !== '0.00') {
      <p class="muted small">Online payment isn't set up here; pay at the office.</p>
    }
  `,
})
export class PayOnline {
  readonly statement = input.required<FeeStatement>();
  /** Where orders are created: student/fees/orders or family/children/<id>/fees/orders. */
  readonly orders = input.required<string>();
  readonly ordered = output<void>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly busy = signal(false);

  protected pay(invoice: string): void {
    this.busy.set(true);
    this.api.post<FeePayment>(this.orders(), { invoice }).subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show('Payment started. It shows as received once the provider confirms it.');
        this.ordered.emit();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
