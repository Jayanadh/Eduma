import { Component, inject, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { date, readable } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { ApplicationT, InternshipT, OpportunityT, ROW_STYLES } from './types';

type ReportRow = { opportunity: string; employer: string; kind: string; applied: number; offers: number; accepted: number };
type AlumnusT = { student: { number: string; name: string }; email: string; phone: string; occupation: string };

/** The placement office (S10C-05..07): opportunities, applications up to an offer, internships and consented alumni. */
@Component({
  selector: 'app-placements-page',
  imports: [PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Academics" title="Placements" subtitle="Students apply with their consent; offers and accepted placements are counted apart." />
      <section class="card stack section">
        <h2 class="card-title">Opportunities</h2>
        <ul class="rows">
          @for (o of opportunities.value() ?? []; track o.id) {
            <li>
              <span><strong>{{ o.title }}</strong> {{ o.employer }} <span class="muted small">· {{ o.kind }} · closes {{ date(o.closes_on) }}{{ o.min_cgpa ? ' · CGPA ' + o.min_cgpa + '+' : '' }}{{ o.programs.length ? ' · ' + o.programs.join(', ') : '' }}</span></span>
              <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Applications for ' + o.title" (click)="open.set(o.id)">Applications</button>
            </li>
          } @empty {
            <li class="muted small">No opportunities yet.</li>
          }
        </ul>
        @if (open()) {
          <h3 class="card-title">Applications</h3>
          <ul class="rows">
            @for (a of applications.value() ?? []; track a.id) {
              <li>
                <span>{{ a.student?.name }} <span class="muted small">{{ a.student?.number }} · {{ readable(a.state) }} · CGPA {{ a.eligibility?.cgpa ?? 'none yet' }}</span></span>
                <span class="actions">
                  @if (a.state === 'applied') { <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Shortlist ' + a.student?.name" (click)="move(a, 'shortlisted')">Shortlist</button> }
                  @if (a.state === 'applied' || a.state === 'shortlisted') {
                    <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Offer ' + a.student?.name" (click)="move(a, 'offered')">Offer</button>
                    <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Decline ' + a.student?.name" (click)="move(a, 'rejected')">Not selected</button>
                  }
                </span>
              </li>
            } @empty {
              <li class="muted small">No applications yet.</li>
            }
          </ul>
        }
        <form id="add-opportunity" class="row" (submit)="$event.preventDefault(); add($any($event.target))">
          <div class="field"><label for="opp-employer">Employer</label>
            <select id="opp-employer">@for (e of employers.value() ?? []; track e.id) { <option [value]="e.id">{{ e.name }}</option> }</select></div>
          <div class="field grow"><label for="opp-title">Title</label><input id="opp-title" maxlength="150" required /></div>
          <div class="field"><label for="opp-kind">Kind</label><select id="opp-kind"><option value="job">Job</option><option value="internship">Internship</option></select></div>
          <div class="field"><label for="opp-cgpa">Minimum CGPA</label><input id="opp-cgpa" inputmode="decimal" /></div>
          <div class="field"><label for="opp-closes">Closes on</label><input id="opp-closes" type="date" required /></div>
          <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Add opportunity</button>
        </form>
        <form id="add-employer" class="row" (submit)="$event.preventDefault(); addEmployer($any($event.target))">
          <div class="field grow"><label for="employer-name">Employer</label><input id="employer-name" maxlength="150" required /></div>
          <div class="field grow"><label for="employer-contact">Contact</label><input id="employer-contact" maxlength="150" /></div>
          <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add employer</button>
        </form>
      </section>
      <section class="card stack section">
        <h2 class="card-title">Report</h2>
        <ul class="rows">
          @for (r of report.value() ?? []; track r.opportunity) {
            <li><span>{{ r.opportunity }} <span class="muted small">{{ r.employer }}</span></span><span class="small">{{ r.applied }} applied · {{ r.offers }} offers · {{ r.accepted }} accepted</span></li>
          }
        </ul>
      </section>
      <section class="card stack section">
        <h2 class="card-title">Internships</h2>
        <ul class="rows">
          @for (i of internships.value() ?? []; track i.id) {
            <li>
              <span>{{ i.student.name }} <span class="muted small">· {{ i.opportunity }}, {{ i.employer }} · supervisor {{ i.supervisor ?? 'not assigned' }}{{ i.score ? ' · scored ' + i.score : '' }}</span></span>
              <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Supervisor for ' + i.student.name" (click)="supervise(i)">Supervisor</button>
            </li>
          } @empty {
            <li class="muted small">No internships yet.</li>
          }
        </ul>
      </section>
      <section class="card stack section">
        <h2 class="card-title">Alumni who agreed to be listed</h2>
        <ul class="rows">
          @for (a of alumni.value() ?? []; track a.student.number) {
            <li><span>{{ a.student.name }} <span class="muted small">{{ a.occupation }}</span></span><span class="small">{{ a.email }} {{ a.phone }}</span></li>
          } @empty {
            <li class="muted small">Nobody yet.</li>
          }
        </ul>
      </section>
    </div>
  `,
  styles: [ROW_STYLES],
})
export class PlacementsPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly dialog = inject(ConfirmDialog);
  protected readonly date = date;
  protected readonly readable = readable;
  protected readonly open = signal('');
  protected readonly employers = load(() => this.api.get<{ id: string; name: string }[]>('development/employers'));
  protected readonly opportunities = load(() => this.api.get<OpportunityT[]>('development/opportunities'));
  protected readonly applications = load(
    () => (this.open() ? this.api.get<ApplicationT[]>(`development/opportunities/${this.open()}/applications`) : of([])),
    () => this.open(),
  );
  protected readonly report = load(() => this.api.get<ReportRow[]>('development/placement-report'));
  protected readonly internships = load(() => this.api.get<InternshipT[]>('development/internships'));
  protected readonly alumni = load(() => this.api.get<AlumnusT[]>('development/alumni'));
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        for (const list of [this.employers, this.opportunities, this.applications, this.report, this.internships]) {
          list.reload();
        }
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected move(a: ApplicationT, state: 'shortlisted' | 'offered' | 'rejected'): void {
    this.run(this.api.post(`development/applications/${a.id}/state`, { state }), 'Updated.');
  }

  protected add(form: HTMLFormElement): void {
    const f = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
    const body = { employer: f('opp-employer'), title: f('opp-title'), kind: f('opp-kind'), min_cgpa: f('opp-cgpa') || null, closes_on: f('opp-closes') };
    this.run(this.api.post('development/opportunities', body), 'Opportunity added.', () => form.reset());
  }

  protected addEmployer(form: HTMLFormElement): void {
    const f = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!.value.trim();
    this.run(this.api.post('development/employers', { name: f('employer-name'), contact: f('employer-contact') }), 'Employer added.', () => form.reset());
  }

  protected async supervise(i: InternshipT): Promise<void> {
    const username = await this.dialog.prompt({ title: `Supervisor for ${i.student.name}`, label: 'Username of the staff supervisor', confirmLabel: 'Assign', required: true });
    if (username) {
      this.run(this.api.post(`development/internships/${i.id}/supervisor`, { username }), 'Supervisor assigned.');
    }
  }
}
