import { Component, computed, inject, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage, isProblem } from '../../core/api-error';
import { OwnRegistration, Registration } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from '../apply/portal-frame';
import { RULES } from '../academics/registration-rules';

/** A student's course registration (SCR-028): choose offerings, confirm, see the result; a choice alone holds no seat. */
@Component({
  selector: 'app-registration-page',
  imports: [LoadError, PortalFrame],
  template: `
    <app-portal-frame heading="Registration">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as d) {
        @if (d.window; as w) {
          <p class="small">
            <strong>{{ w.year }} {{ w.term }}</strong> · {{ w.open ? 'open' : 'opens ' + date(w.opens_on) }} until {{ date(w.closes_on) }} ·
            drop until {{ date(w.drop_until) }} · up to {{ w.max_credits }} credits{{ w.needs_approval ? ' · your adviser approves each choice' : '' }}
          </p>
          <section class="card stack">
            <h2 class="card-title">Choose courses</h2>
            <ul class="rows">
              @for (o of d.offerings; track o.id) {
                <li>
                  <label class="choice">
                    <input type="checkbox" [id]="'choose-' + o.id" [checked]="chosen().has(o.id)" (change)="toggle(o.id, $any($event.target).checked)" />
                    <span><strong>{{ o.label }}</strong> {{ o.title }} <span class="muted small meta">{{ o.credits }} credits · {{ o.seats_left }} seats left{{ o.linked_to ? ' · lab' : '' }}</span></span>
                  </label>
                  @if (o.problems.length) { <span class="small warn">{{ words(o.problems) }}</span> }
                </li>
              } @empty {
                <li class="muted small">Nothing is offered for your regulation this term.</li>
              }
            </ul>
            <div class="summary">
              <span class="small"><strong>{{ chosen().size }}</strong> chosen · {{ credits() }} credits{{ failed() ? ' · not confirmed' : '' }}</span>
              <button type="button" class="btn btn-primary btn-sm" [disabled]="busy() || !chosen().size" (click)="confirm(false)">Confirm registration</button>
              @if (full()) {
                <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="confirm(true)">Join the waitlist</button>
              }
            </div>
            @if (failed(); as message) { <p class="field-error" role="alert">{{ message }}</p> }
          </section>
        } @else {
          <p class="notice notice-info">Registration isn't open for any term right now.</p>
        }
        <section class="card stack">
          <h2 class="card-title">Your registrations</h2>
          <ul class="rows">
            @for (r of d.registrations; track r.id) {
              <li>
                <span><strong>{{ r.offering.label }}</strong> {{ r.offering.title }} <span class="muted small meta">{{ r.offering.term }} · {{ r.state_label }}{{ r.reason_code ? ' (' + (rules[r.reason_code] ?? r.reason_code) + ')' : '' }}</span></span>
                @if (r.state === 'registered' || r.state === 'waitlisted' || r.state === 'pending_approval') {
                  <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Drop ' + r.offering.label" [disabled]="busy()" (click)="drop(r)">Drop</button>
                }
              </li>
            } @empty {
              <li class="muted small">None yet.</li>
            }
          </ul>
        </section>
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </app-portal-frame>
  `,
  styles: `
    .choice {
      display: flex;
      gap: 8px;
      align-items: baseline;
    }

    .warn {
      color: var(--warning-text, var(--text-muted));
    }

    .summary {
      position: sticky;
      bottom: 0;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      padding: 10px 0;
      background: var(--surface);
    }
  `,
})
export class RegistrationPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly confirmDialog = inject(ConfirmDialog);
  protected readonly date = date;
  protected readonly rules = RULES;
  protected readonly data = load(() => this.api.get<OwnRegistration>('student/registration'));
  protected readonly chosen = signal<ReadonlySet<string>>(new Set());
  protected readonly busy = signal(false);
  protected readonly failed = signal('');
  protected readonly full = signal(false);
  protected readonly credits = computed(() =>
    (this.data.value()?.offerings ?? [])
      .filter((o) => this.chosen().has(o.id))
      .reduce((sum, o) => sum + Number(o.credits), 0),
  );

  protected words(codes: string[]): string {
    return codes.map((code) => RULES[code] ?? code).join(' · ');
  }

  protected toggle(id: string, on: boolean): void {
    this.chosen.update((ids) => {
      const next = new Set(ids);
      if (on) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  }

  protected confirm(waitlist: boolean): void {
    this.busy.set(true);
    this.failed.set('');
    this.full.set(false);
    this.api.post<Registration[]>('student/registration', { offerings: [...this.chosen()], waitlist }).subscribe({
      next: (made) => {
        this.busy.set(false);
        this.chosen.set(new Set());
        this.toasts.show(made.map((r) => `${r.offering.label}: ${r.state_label}`).join(' · '));
        this.data.reload();
      },
      error: (err) => {
        // The choices stay, labelled unconfirmed; a full course can go on the waitlist instead.
        this.busy.set(false);
        this.full.set(isProblem(err, 'capacity_exhausted') && this.chosen().size === 1);
        this.failed.set(apiErrorMessage(err));
      },
    });
  }

  protected async drop(r: Registration): Promise<void> {
    const yes = await this.confirmDialog.ask({
      title: `Drop ${r.offering.label}?`,
      message: 'Your seat goes to the next person waiting.',
      confirmLabel: 'Drop',
    });
    if (!yes) {
      return;
    }
    this.busy.set(true);
    this.api.post<Registration>(`student/registrations/${r.id}/drop`, { version: r.version }).subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(`${r.offering.label} dropped.`);
        this.data.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
