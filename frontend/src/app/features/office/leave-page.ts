import { Component, inject, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AuthStore } from '../../core/auth-store';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { OFFICE_STYLES } from './office-styles';

export type LeaveKind = { id: string; code: string; name: string; days_per_year: number; paid: boolean };
type Balance = { code: string; name: string; entitled: number; taken: number; waiting: number; left: number };
type LeaveRequestT = {
  id: string;
  employee: { id: string; number: string; name: string };
  leave_type: { id: string; code: string; name: string; paid: boolean };
  starts_on: string;
  ends_on: string;
  days: number;
  reason: string;
  state: 'submitted' | 'approved' | 'rejected' | 'canceled';
  decided_by: string | null;
};
type LeaveList = { requests: LeaveRequestT[]; balances: Balance[] };

const STATES = { submitted: 'waiting for approval', approved: 'approved', rejected: 'rejected', canceled: 'canceled' };

/** Every staff member's own leave and balances (S10B-01, S10B-03); approvers also decide other people's requests. */
@Component({
  selector: 'app-leave-page',
  imports: [PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="People" title="Leave" subtitle="Your leave and what is left this year. Someone else approves it." />
      <section class="card stack section">
        <h2 class="card-title">This year</h2>
        <ul class="rows">
          @for (b of mine.value()?.balances ?? []; track b.code) {
            <li><strong>{{ b.name }}</strong><span class="muted small">{{ b.left }} of {{ b.entitled }} days left{{ b.waiting ? ' · ' + b.waiting + ' waiting' : '' }}</span></li>
          } @empty {
            <li class="muted small">No leave types are set up yet.</li>
          }
        </ul>
        <form id="ask-leave" class="row" (submit)="$event.preventDefault(); ask($any($event.target))">
          <div class="field"><label for="leave-type">Type</label>
            <select id="leave-type">@for (k of kinds.value() ?? []; track k.id) { <option [value]="k.id">{{ k.name }}</option> }</select></div>
          <div class="field"><label for="leave-from">From</label><input id="leave-from" type="date" required /></div>
          <div class="field"><label for="leave-to">To</label><input id="leave-to" type="date" required /></div>
          <div class="field grow"><label for="leave-reason">Reason</label><input id="leave-reason" maxlength="300" required /></div>
          <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Ask for leave</button>
        </form>
      </section>
      <section class="card stack section">
        <h2 class="card-title">Your requests</h2>
        <ul class="rows">
          @for (r of mine.value()?.requests ?? []; track r.id) {
            <li>
              <span>{{ r.leave_type.name }} <span class="muted small">· {{ date(r.starts_on) }}–{{ date(r.ends_on) }} · {{ r.days }} days · {{ states[r.state] }}</span></span>
              @if (r.state === 'submitted' || r.state === 'approved') {
                <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Cancel leave from ' + date(r.starts_on)" (click)="act(r, 'cancel')">Cancel</button>
              }
            </li>
          } @empty {
            <li class="muted small">No requests yet.</li>
          }
        </ul>
      </section>
      @if (approver) {
        <section class="card stack section">
          <h2 class="card-title">Waiting for your decision</h2>
          <ul class="rows">
            @for (r of waiting.value()?.requests ?? []; track r.id) {
              <li>
                <span><strong>{{ r.employee.name }}</strong> {{ r.leave_type.name }} <span class="muted small">· {{ date(r.starts_on) }}–{{ date(r.ends_on) }} · {{ r.days }} days · {{ r.reason }}</span></span>
                <span class="actions">
                  <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve leave for ' + r.employee.name" (click)="act(r, 'approve')">Approve</button>
                  <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Reject leave for ' + r.employee.name" (click)="act(r, 'reject')">Reject</button>
                </span>
              </li>
            } @empty {
              <li class="muted small">Nothing waiting.</li>
            }
          </ul>
        </section>
      }
    </div>
  `,
  styles: [OFFICE_STYLES],
})
export class LeavePage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly states = STATES;
  protected readonly approver = inject(AuthStore).can('hr.leave_approve');
  protected readonly kinds = load(() => this.api.get<LeaveKind[]>('institution/hr/leave-types'));
  protected readonly mine = load(() => this.api.get<LeaveList>('institution/hr/leave'));
  protected readonly waiting = load(() =>
    this.approver ? this.api.get<LeaveList>('institution/hr/leave', { all: 1, state: 'submitted' }) : of(null),
  );
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        this.mine.reload();
        this.waiting.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected ask(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
    const body = { leave_type: field('leave-type'), starts_on: field('leave-from'), ends_on: field('leave-to'), reason: field('leave-reason') };
    this.run(this.api.post('institution/hr/leave', body), 'Leave asked for.', () => form.reset());
  }

  protected act(r: LeaveRequestT, action: 'approve' | 'reject' | 'cancel'): void {
    const words = { approve: 'Leave approved.', reject: 'Leave rejected.', cancel: 'Leave canceled; the days are back.' };
    this.run(this.api.post(`institution/hr/leave/${r.id}/${action}`, {}), words[action]);
  }
}
