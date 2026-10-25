import { Component, computed, inject, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { StatusBadge } from '../../ui/status-badge';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AuthStore } from '../../core/auth-store';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from '../apply/portal-frame';
import { ApplicationT, OpportunityT, ScholarT } from '../development/types';

type OwnPlacements = {
  opportunities: (OpportunityT & { eligibility: { eligible: boolean; reasons: string[] } })[];
  applications: ApplicationT[];
  alumni: { email: string; phone: string; occupation: string; listed: boolean } | null;
};

/** A student's placements, offers, alumni listing and research milestones (S10C-05, S10C-07, S10C-08). */
@Component({
  selector: 'app-careers-page',
  imports: [LoadError, PortalFrame, StatusBadge],
  template: `
    <app-portal-frame heading="Careers and research">
      @if (placements()) {
        <app-load-error [message]="data.error()" (retry)="data.reload()" />
        @if (data.value(); as d) {
          <section class="card stack section">
            <h2 class="card-title">Open opportunities</h2>
            <ul class="rows">
              @for (o of d.opportunities; track o.id) {
                <li>
                  <span><strong>{{ o.title }}</strong> {{ o.employer }} <span class="muted small meta">{{ o.kind }} · closes {{ date(o.closes_on) }}</span>
                    @if (!o.eligibility.eligible) { <span class="muted small"> · {{ o.eligibility.reasons.join(' ') }}</span> }</span>
                  @if (o.eligibility.eligible && !applied(o.id)) {
                    <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Apply for ' + o.title" (click)="apply(o)">Apply</button>
                  }
                </li>
              } @empty {
                <li class="muted small">Nothing open right now.</li>
              }
            </ul>
          </section>
          <section class="card stack section">
            <h2 class="card-title">Your applications</h2>
            <ul class="rows">
              @for (a of d.applications; track a.id) {
                <li>
                  <span>{{ a.opportunity.title }} <app-status-badge [status]="a.state" /><span class="muted small meta">{{ a.opportunity.employer }}</span></span>
                  <span class="actions">
                    @if (a.state === 'offered') {
                      <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Accept ' + a.opportunity.title" (click)="decide(a, 'accept')">Accept</button>
                      <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Decline ' + a.opportunity.title" (click)="decide(a, 'decline')">Decline</button>
                    }
                    @if (a.state === 'applied' || a.state === 'shortlisted') {
                      <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Withdraw from ' + a.opportunity.title" (click)="decide(a, 'withdraw')">Withdraw</button>
                    }
                  </span>
                </li>
              } @empty {
                <li class="muted small">No applications yet.</li>
              }
            </ul>
          </section>
          <form id="alumni" class="card stack section" (submit)="$event.preventDefault(); saveAlumni($any($event.target))">
            <h2 class="card-title">Alumni list</h2>
            <p class="muted small">{{ d.alumni?.listed ? 'You are on the alumni list. Only the placement office sees it.' : 'Join so the placement office can stay in touch after you leave. You can leave the list any time.' }}</p>
            <div class="field"><label for="alumni-email">Email</label><input id="alumni-email" type="email" [value]="d.alumni?.email ?? ''" /></div>
            <div class="field"><label for="alumni-phone">Phone</label><input id="alumni-phone" [value]="d.alumni?.phone ?? ''" /></div>
            <div class="field"><label for="alumni-job">Work or study</label><input id="alumni-job" [value]="d.alumni?.occupation ?? ''" /></div>
            <label><input id="alumni-consent" type="checkbox" [checked]="d.alumni?.listed ?? false" /> I agree to be listed and contacted by the institution</label>
            <div class="actions">
              <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Save</button>
              @if (d.alumni?.listed) { <button type="button" class="btn btn-secondary btn-sm" (click)="leave()">Leave the list</button> }
            </div>
          </form>
        }
      }
      @if (research.value(); as s) {
        <section class="card stack section">
          <h2 class="card-title">Research: {{ s.topic }}</h2>
          <ul class="rows">
            @for (m of s.milestones; track m.id) {
              <li>
                <span>{{ m.title }} <app-status-badge [status]="m.state" /><span class="muted small meta">due {{ date(m.due_on) }}{{ m.note ? ' · ' + m.note : '' }}</span></span>
                @if (m.state === 'pending' || m.state === 'returned') {
                  <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Submit ' + m.title" (click)="submit(m.id, m.title)">Submit</button>
                }
              </li>
            }
          </ul>
        </section>
      }
    </app-portal-frame>
  `,
  styles: `
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

  `,
})
export class CareersPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly auth = inject(AuthStore);
  private readonly dialog = inject(ConfirmDialog);
  protected readonly date = date;
  protected readonly placements = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('placements') ?? false);
  private readonly quality = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('quality') ?? false);
  protected readonly data = load(() => (this.placements() ? this.api.get<OwnPlacements>('student/placements') : of(null)));
  protected readonly research = load(() => (this.quality() ? this.api.get<ScholarT | null>('student/research') : of(null)));
  protected readonly busy = signal(false);

  protected applied(id: string): boolean {
    return (this.data.value()?.applications ?? []).some((a) => a.opportunity.id === id);
  }

  private run(request: Observable<unknown>, done: string): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        this.data.reload();
        this.research.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected async apply(o: OpportunityT): Promise<void> {
    const consent = await this.dialog.ask({
      title: `Apply for ${o.title}?`,
      message: `Your name, program and CGPA will be shared with ${o.employer} for this opportunity only.`,
      confirmLabel: 'I agree, apply',
    });
    if (consent) {
      this.run(this.api.post(`student/placements/${o.id}/apply`, { consent: true }), 'Applied.');
    }
  }

  protected decide(a: ApplicationT, decision: 'accept' | 'decline' | 'withdraw'): void {
    this.run(this.api.post(`student/placement-applications/${a.id}/decide`, { decision }), 'Done.');
  }

  protected saveAlumni(form: HTMLFormElement): void {
    const f = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!;
    const body = { consent: f('alumni-consent').checked, email: f('alumni-email').value.trim(), phone: f('alumni-phone').value.trim(), occupation: f('alumni-job').value.trim() };
    this.run(this.api.put('student/alumni', body), 'Saved.');
  }

  protected leave(): void {
    this.run(this.api.delete('student/alumni'), 'You have left the alumni list; your contact details were removed.');
  }

  protected async submit(id: string, title: string): Promise<void> {
    const summary = await this.dialog.prompt({ title: `Submit ${title}`, label: 'What you have done', type: 'textarea', confirmLabel: 'Submit', required: true });
    if (summary) {
      this.run(this.api.post(`student/research/milestones/${id}/submit`, { summary }), 'Submitted to your supervisor.');
    }
  }
}
