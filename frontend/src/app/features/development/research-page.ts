import { Component, inject, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { StatusBadge } from '../../ui/status-badge';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { ROW_STYLES, ScholarT } from './types';

/** The research office (S10C-08): scholars, supervisors, ethics approvals with their dates, and milestones. */
@Component({
  selector: 'app-research-page',
  imports: [PageHeader, StatusBadge],
  template: `
    <div class="page">
      <app-page-header eyebrow="Academics" title="Research" subtitle="Supervisors approve milestones; work that needs ethics approval waits for a valid one." />
      @for (s of scholars.value() ?? []; track s.id) {
        <section class="card stack section">
          <h2 class="card-title">{{ s.student.name }} · {{ s.topic }}</h2>
          <p class="small">
            @for (x of s.supervisors; track x.id) {
              <span class="part">{{ x.name }} ({{ x.role }}){{ x.current ? '' : ', ended' }}
                @if (x.current) { <button type="button" class="link small" [attr.aria-label]="'End supervision by ' + x.name" (click)="end(x.id)">end</button> }</span>
            } @empty { No supervisor yet. }
          </p>
          <p class="small">@for (e of s.ethics; track e.reference) { <span class="part">{{ e.reference }} {{ date(e.valid_from) }}–{{ date(e.valid_to) }}{{ e.valid ? '' : ' (not valid today)' }}</span> } @empty { No ethics approval recorded. }</p>
          <ul class="rows">
            @for (m of s.milestones; track m.id) {
              <li><span>{{ m.title }} <app-status-badge [status]="m.state" /><span class="muted small meta">due {{ date(m.due_on) }}{{ m.needs_ethics ? ' · needs ethics approval' : '' }}</span></span></li>
            }
          </ul>
          <span class="actions">
            <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Add supervisor for ' + s.student.name" (click)="supervisor(s)">Add supervisor</button>
            <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Add milestone for ' + s.student.name" (click)="milestone(s)">Add milestone</button>
          </span>
          <form class="row" [id]="'ethics-' + s.id" (submit)="$event.preventDefault(); ethics(s, $any($event.target))">
            <div class="field"><label [for]="'eth-ref-' + s.id">Ethics reference</label><input [id]="'eth-ref-' + s.id" class="eth-ref" required /></div>
            <div class="field grow"><label [for]="'eth-com-' + s.id">Committee</label><input [id]="'eth-com-' + s.id" class="eth-com" required /></div>
            <div class="field"><label [for]="'eth-from-' + s.id">Valid from</label><input [id]="'eth-from-' + s.id" class="eth-from" type="date" required /></div>
            <div class="field"><label [for]="'eth-to-' + s.id">Valid to</label><input [id]="'eth-to-' + s.id" class="eth-to" type="date" required /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Record approval</button>
          </form>
        </section>
      } @empty {
        <p class="muted small">No research scholars yet.</p>
      }
      <form id="add-scholar" class="card row section" (submit)="$event.preventDefault(); add($any($event.target))">
        <div class="field"><label for="scholar-number">Student number</label><input id="scholar-number" required /></div>
        <div class="field grow"><label for="scholar-topic">Topic</label><input id="scholar-topic" maxlength="250" required /></div>
        <div class="field"><label for="scholar-start">Started on</label><input id="scholar-start" type="date" required /></div>
        <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Add scholar</button>
      </form>
    </div>
  `,
  styles: [ROW_STYLES, `.part + .part::before { content: ' · '; } .link { background: none; border: 0; color: var(--primary-text); cursor: pointer; }`],
})
export class ResearchPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly dialog = inject(ConfirmDialog);
  protected readonly date = date;
  protected readonly scholars = load(() => this.api.get<ScholarT[]>('development/scholars'));
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        this.scholars.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected add(form: HTMLFormElement): void {
    const f = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!.value.trim();
    const number = f('scholar-number');
    this.api.get<{ results: { id: string; number: string }[] }>('institution/students', { search: number }).subscribe({
      next: (found) => {
        const student = found.results.find((s) => s.number === number);
        if (!student) {
          this.toasts.show(`No student ${number}.`, 'danger');
          return;
        }
        this.run(this.api.post('development/scholars', { student: student.id, topic: f('scholar-topic'), started_on: f('scholar-start') }), 'Scholar added.', () => form.reset());
      },
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }

  protected async supervisor(s: ScholarT): Promise<void> {
    const username = await this.dialog.prompt({ title: `Supervisor for ${s.student.name}`, label: 'Username', confirmLabel: 'Add', required: true });
    if (username) {
      this.run(this.api.post(`development/scholars/${s.id}/supervisors`, { username, role: s.supervisors.some((x) => x.current) ? 'co' : 'main' }), 'Supervisor added.');
    }
  }

  protected async milestone(s: ScholarT): Promise<void> {
    const title = await this.dialog.prompt({ title: `Milestone for ${s.student.name}`, label: 'Milestone', confirmLabel: 'Next', required: true });
    const due = title && (await this.dialog.prompt({ title, label: 'Due on', type: 'date', confirmLabel: 'Next', required: true }));
    if (title && due) {
      const ethics = await this.dialog.ask({ title, message: 'Does this work need an ethics approval?', confirmLabel: 'Yes, it needs one', cancelLabel: 'No' });
      this.run(this.api.post(`development/scholars/${s.id}/milestones`, { title, due_on: due, needs_ethics: ethics }), 'Milestone added.');
    }
  }

  protected ethics(s: ScholarT, form: HTMLFormElement): void {
    const f = (cls: string) => form.querySelector<HTMLInputElement>(`.${cls}`)!.value.trim();
    const body = { reference: f('eth-ref'), committee: f('eth-com'), valid_from: f('eth-from'), valid_to: f('eth-to') };
    this.run(this.api.post(`development/scholars/${s.id}/ethics`, body), 'Approval recorded.', () => form.reset());
  }

  protected end(id: string): void {
    this.run(this.api.post(`development/supervisions/${id}/end`, {}), 'Supervision ended; they no longer see this scholar.');
  }
}
