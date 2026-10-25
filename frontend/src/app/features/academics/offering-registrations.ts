import { Component, inject, input, output, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { Page, Registration } from '../../core/api/types';
import { load } from '../../core/load';
import { ToastService } from '../../ui/toast';
import { RULES } from './registration-rules';

/** An offering's registrations: who holds a seat, who waits for approval, the waitlist in order. */
@Component({
  selector: 'app-offering-registrations',
  template: `
    <section class="card stack section">
      <h2 class="card-title">Registrations</h2>
      <ul class="rows">
        @for (r of rows.value()?.results ?? []; track r.id) {
          <li>
            <span><strong>{{ r.student.number }}</strong> {{ r.student.full_name }} <span class="muted small meta">{{ r.state_label }}{{ r.reason_code ? ' (' + (rules[r.reason_code] ?? r.reason_code) + ')' : '' }}{{ r.overrides.length ? ' · with an override' : '' }}</span></span>
            <span class="actions">
              @if (r.state === 'pending_approval') {
                <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve ' + r.student.number" [disabled]="busy()" (click)="act(r, 'approve')">Approve</button>
              }
              @if (r.state === 'pending_approval' || r.state === 'waitlisted') {
                <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Reject ' + r.student.number" [disabled]="busy()" (click)="act(r, 'reject')">Reject</button>
              }
              @if (r.state === 'registered') {
                <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Drop ' + r.student.number" [disabled]="busy()" (click)="act(r, 'drop')">Drop</button>
              }
            </span>
          </li>
        } @empty {
          <li class="muted small">Nobody has registered yet.</li>
        }
      </ul>
    </section>
  `,
  styles: `
    .actions {
      display: flex;
      gap: 8px;
    }
  `,
})
export class OfferingRegistrations {
  readonly offering = input.required<string>();
  readonly changed = output<void>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly rules = RULES;
  // shortcut: one page of 200; a larger offering needs paging here.
  protected readonly rows = load(
    () => this.api.get<Page<Registration>>('institution/academics/registrations', { offering: this.offering(), page_size: 200 }),
    () => this.offering(),
  );
  protected readonly busy = signal(false);

  protected act(r: Registration, action: 'approve' | 'reject' | 'drop'): void {
    this.busy.set(true);
    this.api.post<Registration>(`institution/academics/registrations/${r.id}/${action}`, { version: r.version }).subscribe({
      next: (done) => {
        this.busy.set(false);
        this.toasts.show(`${r.student.number}: ${done.state_label}.`);
        this.rows.reload();
        this.changed.emit();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
        this.rows.reload();
      },
    });
  }
}
