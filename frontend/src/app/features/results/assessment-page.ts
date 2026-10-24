import { Component, inject, input, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AssessmentT, MarkStatus } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

type Cell = { status: MarkStatus; score: string };

/** One assessment: the marks grid (scores or absent / exempt / withheld — never a silent zero), the steps from draft
 * to published, the results, revaluations and outcome attainment. */
@Component({
  selector: 'app-assessment-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as a) {
        <app-page-header eyebrow="Assessment" [title]="a.title" [subtitle]="a.target.label + (a.subject ? ' · ' + a.subject : '') + ' · ' + a.term.name + ' · ' + a.state_label" backLink="/app/results/assessments">
          @if (a.state === 'draft' && a.can_evaluate) {
            <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="save(a)">Save marks</button>
            <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="step(a, 'submit')">Submit for moderation</button>
          }
          @if (a.state === 'submitted' && can('results.moderate')) {
            <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="step(a, 'moderate')">Approve marks</button>
            <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="back(a)">Return</button>
          }
          @if (a.state === 'moderated' && can('results.publish')) {
            <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="step(a, 'publish')">Publish results</button>
          }
        </app-page-header>
        @if (a.returned_reason) { <p class="notice notice-warning section">Returned: {{ a.returned_reason }}</p> }
        <p class="muted small section">Total = each score ÷ maximum × weight; pass {{ a.scheme.pass_percent }}%@for (c of a.scheme.components; track c.id) { @if (c.min_percent) { · {{ c.name }} needs {{ c.min_percent }}% } }.</p>
        <div class="card section table-card">
          <table>
            <thead><tr><th>Student</th>@for (c of a.scheme.components; track c.id) { <th>{{ c.name }} /{{ c.max_marks }}</th> }<th>Total</th><th>Grade</th><th>Result</th></tr></thead>
            <tbody>
              @for (cand of a.candidates; track cand.id) {
                <tr>
                  <td><strong>{{ cand.student.number }}</strong> {{ cand.student.full_name }}</td>
                  @for (c of a.scheme.components; track c.id) {
                    <td>
                      @if (a.state === 'draft' && a.can_evaluate) {
                        @let cell = cellOf(a, cand.id, c.id);
                        <span class="cell">
                          <label class="sr-only" [for]="'status-' + cand.id + '-' + c.id">{{ c.name }} status for {{ cand.student.full_name }}</label>
                          <select [id]="'status-' + cand.id + '-' + c.id" (change)="set(cand.id, c.id, { status: $any($event.target).value, score: cell.score })">
                            @for (s of statuses; track s[0]) { <option [value]="s[0]" [selected]="cell.status === s[0]">{{ s[1] }}</option> }
                          </select>
                          @if (cell.status === 'scored') {
                            <label class="sr-only" [for]="'score-' + cand.id + '-' + c.id">{{ c.name }} score for {{ cand.student.full_name }}</label>
                            <input [id]="'score-' + cand.id + '-' + c.id" type="number" min="0" [max]="c.max_marks" step="0.5" [value]="cell.score" (input)="set(cand.id, c.id, { status: 'scored', score: $any($event.target).value })" />
                          }
                        </span>
                      } @else {
                        {{ shown(cand.marks[c.id]) }}
                      }
                    </td>
                  }
                  <td>{{ cand.result?.total ?? '' }}</td>
                  <td>{{ cand.result?.grade ?? '' }}</td>
                  <td>
                    {{ cand.result ? cand.result.outcome + (cand.result.revision > 1 ? ' (rev ' + cand.result.revision + ')' : '') : '' }}
                    @if (cand.result?.failed_components?.length) { <span class="muted small"> · {{ cand.result?.failed_components?.join(', ') }} below minimum</span> }
                    @if (a.state === 'published' && (can('results.moderate') || can('results.publish'))) {
                      <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Revalue ' + cand.student.number" (click)="revaluing.set(cand.id)">Revalue</button>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        @if (revaluing(); as candidate) {
          <form id="revalue" class="card stack section" (submit)="$event.preventDefault(); revalue(a, candidate, $any($event.target))">
            <h2 class="card-title">Revaluation</h2>
            <div class="row">
              @for (c of a.scheme.components; track c.id) {
                <div class="field"><label [for]="'re-' + c.id">{{ c.name }} (blank: unchanged)</label><input [id]="'re-' + c.id" type="number" min="0" [max]="c.max_marks" /></div>
              }
              <div class="field grow"><label for="re-reason">Reason</label><input id="re-reason" /></div>
            </div>
            <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Ask for approval</button></div>
          </form>
        }
        @if (a.cases.length) {
          <section class="card stack section">
            <h2 class="card-title">Revaluations waiting</h2>
            @for (c of a.cases; track c.id) {
              <p class="small">{{ c.student }}: {{ c.reason }} <span class="muted">· {{ c.requested_by }}</span>
                @if (can('results.publish')) {
                  <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve revaluation ' + c.student" (click)="decide(c.id, 'approve')">Approve</button>
                  <button type="button" class="btn btn-secondary btn-sm" (click)="decide(c.id, 'reject')">Reject</button>
                }
              </p>
            }
          </section>
        }
        @if (a.target.kind === 'offering' && can('assessment.manage')) {
          <section class="card stack section">
            <h2 class="card-title">Course outcomes</h2>
            <p class="small">@for (m of a.mappings; track $index) { <span class="part">{{ componentName(a, m.component) }} → {{ m.outcome }}</span> } @empty { <span class="muted">No components mapped.</span> }</p>
            <form id="map-outcome" class="row" (submit)="$event.preventDefault(); map(a, $any($event.target))">
              <div class="field"><label for="map-component">Component</label>
                <select id="map-component">@for (c of a.scheme.components; track c.id) { <option [value]="c.id">{{ c.name }}</option> }</select></div>
              <div class="field"><label for="map-outcome-code">Outcome</label>
                <select id="map-outcome-code">@for (o of outcomes.value() ?? []; track o.id) { <option [value]="o.id">{{ o.code }} · {{ o.description }}</option> }</select></div>
              <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Map</button>
            </form>
            @if (a.state === 'published') {
              <div><button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="attain(a)">Work out attainment (60%)</button></div>
            }
            @if (a.attainment; as run) {
              <p class="small">@for (r of run.results; track r.outcome) { <span class="part">{{ r.outcome }}: {{ r.attained }} of {{ r.candidates }} ({{ r.percent ?? '—' }}%)</span> }</p>
              <p class="muted small">Evidence from marked work at {{ run.threshold_percent }}%; not a claim of accreditation.</p>
            }
          </section>
        }
      }
    </div>
  `,
  styles: `
    .table-card {
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;

      th,
      td {
        padding: 6px 8px;
        text-align: left;
        vertical-align: top;
        border-bottom: 1px solid var(--border);
      }
    }

    .cell {
      display: flex;
      gap: 4px;

      input {
        width: 5.5em;
      }
    }

    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: end;
    }

    .grow {
      flex: 1 1 180px;
    }

    .part + .part::before {
      content: ' · ';
    }
  `,
})
export class AssessmentPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly auth = inject(AuthStore);
  private readonly toasts = inject(ToastService);
  private readonly confirm = inject(ConfirmDialog);
  protected readonly statuses: [MarkStatus, string][] = [
    ['scored', 'Score'],
    ['absent', 'Absent'],
    ['exempt', 'Exempt'],
    ['withheld', 'Withheld'],
  ];
  protected readonly data = load(
    () => this.api.get<AssessmentT>(`institution/results/assessments/${this.id()}`),
    () => this.id(),
  );
  protected readonly outcomes = load(
    () => {
      const a = this.data.value();
      return a?.course && this.can('assessment.manage')
        ? this.api.get<{ id: string; code: string; description: string }[]>(`institution/results/courses/${a.course?.id}/outcomes`)
        : of([]);
    },
    () => this.data.value()?.id,
  );
  /** Marks typed on this page, by candidate then component, not yet saved. */
  private readonly edits = signal<Record<string, Record<string, Cell>>>({});
  protected readonly revaluing = signal<string | null>(null);
  protected readonly busy = signal(false);

  protected can(perm: string): boolean {
    return this.auth.can(perm);
  }

  protected cellOf(a: AssessmentT, candidate: string, component: string): Cell {
    const edited = this.edits()[candidate]?.[component];
    if (edited) {
      return edited;
    }
    const saved = a.candidates.find((c) => c.id === candidate)?.marks[component];
    return { status: saved?.status ?? 'scored', score: saved?.score ?? '' };
  }

  protected set(candidate: string, component: string, cell: Cell): void {
    this.edits.update((all) => ({ ...all, [candidate]: { ...all[candidate], [component]: cell } }));
  }

  protected shown(mark: { status: MarkStatus; score: string | null } | undefined): string {
    if (!mark) {
      return 'missing';
    }
    return mark.status === 'scored' ? (mark.score ?? '') : mark.status;
  }

  protected componentName(a: AssessmentT, id: string): string {
    return a.scheme.components.find((c) => c.id === id)?.name ?? id;
  }

  private run(request: Observable<unknown>, message: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(message);
        after?.();
        this.data.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
        this.data.reload();
      },
    });
  }

  protected save(a: AssessmentT): void {
    const marks = Object.entries(this.edits()).flatMap(([candidate, cells]) =>
      Object.entries(cells)
        .filter(([, cell]) => cell.status !== 'scored' || cell.score !== '')
        .map(([component, cell]) => ({ candidate, component, status: cell.status, score: cell.status === 'scored' ? cell.score : null })),
    );
    this.run(this.api.post(`institution/results/assessments/${a.id}/marks`, { version: a.version, marks }), 'Marks saved.', () =>
      this.edits.set({}),
    );
  }

  protected step(a: AssessmentT, action: 'submit' | 'moderate' | 'publish'): void {
    const words = { submit: 'Submitted for moderation.', moderate: 'Marks approved.', publish: 'Results published.' };
    this.run(this.api.post(`institution/results/assessments/${a.id}/${action}`, { version: a.version }), words[action]);
  }

  protected async back(a: AssessmentT): Promise<void> {
    const reason = await this.confirm.prompt({
      title: 'Return these marks?',
      label: 'What should the teacher check?',
      confirmLabel: 'Return',
      required: true,
    });
    if (reason) {
      this.run(this.api.post(`institution/results/assessments/${a.id}/return`, { version: a.version, reason }), 'Returned to the teacher.');
    }
  }

  protected revalue(a: AssessmentT, candidate: string, form: HTMLFormElement): void {
    const marks: Record<string, { status: string; score: string }> = {};
    for (const c of a.scheme.components) {
      const value = form.querySelector<HTMLInputElement>(`#re-${c.id}`)!.value;
      if (value !== '') {
        marks[c.id] = { status: 'scored', score: value };
      }
    }
    const reason = form.querySelector<HTMLInputElement>('#re-reason')!.value.trim();
    this.run(this.api.post(`institution/results/candidates/${candidate}/cases`, { reason, marks }), 'Revaluation sent for approval.', () =>
      this.revaluing.set(null),
    );
  }

  protected decide(id: string, action: 'approve' | 'reject'): void {
    this.run(this.api.post(`institution/results/cases/${id}/${action}`, {}), action === 'approve' ? 'Revaluation approved.' : 'Revaluation rejected.');
  }

  protected map(a: AssessmentT, form: HTMLFormElement): void {
    const component = form.querySelector<HTMLSelectElement>('#map-component')!.value;
    const outcome = form.querySelector<HTMLSelectElement>('#map-outcome-code')!.value;
    this.run(this.api.post(`institution/results/assessments/${a.id}/mappings`, { component, outcome }), 'Mapped.');
  }

  protected attain(a: AssessmentT): void {
    this.run(this.api.post(`institution/results/assessments/${a.id}/attainment`, { threshold_percent: '60' }), 'Attainment worked out.');
  }
}
