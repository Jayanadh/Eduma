import { Component, computed, inject, input, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { Attempt, CreditTransfer, DegreeProgress, StudentRecord } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { load } from '../../core/load';
import { ToastService } from '../../ui/toast';
import { DegreeProgressView } from '../academics/degree-progress';

/** A college student's academic record: course outcomes, transfer credit and advisory degree progress (S5D). */
@Component({
  selector: 'app-record-section',
  imports: [DegreeProgressView],
  template: `
    <section class="card stack">
      <h2 class="card-title">Academic record</h2>
      @if (progress.value(); as p) {
        <app-degree-progress [progress]="p" />
        @if (canRecord()) {
          <h3 class="card-title">Record an outcome</h3>
          <form id="record-outcome" class="row" (submit)="$event.preventDefault(); record($any($event.target), p.attempts)">
            <div class="field grow">
              <label for="outcome-attempt">Attempt</label>
              <select id="outcome-attempt">
                @for (a of p.attempts; track a.id) { <option [value]="a.id">{{ a.course }} · attempt {{ a.attempt_no }} · {{ a.term }} · {{ a.outcome_label }}</option> }
              </select>
            </div>
            <div class="field">
              <label for="outcome-value">Outcome</label>
              <select id="outcome-value">
                <option value="passed">Passed</option>
                <option value="failed">Failed</option>
                <option value="absent">Absent</option>
                <option value="withheld">Withheld</option>
                <option value="exempt">Exempt</option>
              </select>
            </div>
            <div class="field"><label for="outcome-gp">Grade point</label><input id="outcome-gp" type="number" min="0" max="10" step="0.01" /></div>
            <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy() || !p.attempts.length">Record</button>
          </form>
        }
        <h3 class="card-title">Transfer credit</h3>
        <ul class="rows">
          @for (t of p.transfers; track t.id) {
            <li>
              <span>{{ t.source_course }} <span class="muted small meta">{{ t.source_institution }} · {{ t.source_credits }} credits · {{ t.decision_label }}{{ t.approved_credits ? ' · ' + t.approved_credits + ' accepted' : '' }}{{ t.course ? ' as ' + t.course : '' }}{{ t.awarding_authority ? ' · by ' + t.awarding_authority : '' }}</span></span>
              @if (canRecord() && t.decision === 'pending') {
                <span class="actions">
                  <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve ' + t.source_course" [disabled]="busy()" (click)="decide(t, true)">Approve</button>
                  <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Reject ' + t.source_course" [disabled]="busy()" (click)="decide(t, false)">Reject</button>
                </span>
              }
            </li>
          } @empty {
            <li class="muted small">None.</li>
          }
        </ul>
        @if (canRecord()) {
          <form id="add-transfer" class="row" (submit)="$event.preventDefault(); transfer($any($event.target))">
            <div class="field grow"><label for="transfer-from">From</label><input id="transfer-from" placeholder="Institution" /></div>
            <div class="field grow"><label for="transfer-course">Course</label><input id="transfer-course" /></div>
            <div class="field"><label for="transfer-credits">Credits</label><input id="transfer-credits" type="number" min="0" step="0.5" /></div>
            <div class="field grow"><label for="transfer-evidence">Evidence</label><input id="transfer-evidence" /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add</button>
          </form>
        }
        @if (message(); as m) { <p class="field-error" role="alert">{{ m }}</p> }
      } @else if (progress.error()) {
        <p class="muted small">{{ progress.error() }}</p>
      }
    </section>
  `,
  styles: `
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: end;
    }

    .grow {
      flex: 1 1 160px;
    }

    .actions {
      display: flex;
      gap: 8px;
    }
  `,
})
export class RecordSection {
  readonly student = input.required<StudentRecord>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly auth = inject(AuthStore);
  protected readonly canRecord = computed(() => this.auth.can('academic_record.manage'));
  protected readonly progress = load(
    () => this.api.get<DegreeProgress>(`institution/academics/students/${this.student().id}/progress`),
    () => this.student().id,
  );
  protected readonly busy = signal(false);
  protected readonly message = signal('');

  private run(request: ReturnType<Api['post']>, done: string): void {
    this.busy.set(true);
    this.message.set('');
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        this.progress.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.message.set(apiErrorMessage(err));
      },
    });
  }

  protected record(form: HTMLFormElement, attempts: Attempt[]): void {
    const id = form.querySelector<HTMLSelectElement>('#outcome-attempt')!.value;
    const outcome = form.querySelector<HTMLSelectElement>('#outcome-value')!.value;
    const gp = form.querySelector<HTMLInputElement>('#outcome-gp')!.value;
    const graded = outcome === 'passed' || outcome === 'failed';
    const which = attempts.find((a) => a.id === id);
    this.run(
      this.api.patch(`institution/academics/attempts/${id}`, { outcome, grade_point: graded ? gp || null : null }),
      `${which?.course ?? 'Outcome'} recorded.`,
    );
  }

  protected transfer(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!.value.trim();
    const body = {
      student: this.student().id,
      source_institution: field('transfer-from'),
      source_course: field('transfer-course'),
      source_credits: field('transfer-credits'),
      evidence: field('transfer-evidence'),
    };
    this.run(this.api.post('institution/academics/transfers', body), 'Transfer credit recorded.');
  }

  protected async decide(t: CreditTransfer, approve: boolean): Promise<void> {
    const body = approve
      ? { version: t.version, decision: 'approved', approved_credits: t.source_credits, awarding_authority: 'Board of Studies' }
      : { version: t.version, decision: 'rejected' };
    this.run(this.api.post(`institution/academics/transfers/${t.id}/decide`, body), approve ? 'Approved.' : 'Rejected.');
  }
}
