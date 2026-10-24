import { Component, computed, inject, input, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { BatchRow, SubmissionBatch } from '../../core/api/types';
import { load } from '../../core/load';
import { AuthStore } from '../../core/auth-store';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** One result batch (SCR-031). The college previews exactly what crosses, removes rows with problems, submits and
 * corrects; the university accepts or returns each row with a reason. */
@Component({
  selector: 'app-batch-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as b) {
        <app-page-header
          [eyebrow]="reviewing() ? 'From ' + b.college : 'To ' + b.university"
          [title]="b.program + ' · ' + b.term"
          [subtitle]="'Revision ' + b.revision + ' · ' + b.status_label + ' · ' + b.rows.length + ' students'"
          backLink="/app/affiliations"
        >
          @if (!reviewing() && b.status === 'draft') {
            <button type="button" class="btn btn-primary btn-sm" [disabled]="busy() || blocked()" (click)="submit(b)">Submit to {{ b.university }}</button>
          }
          @if (!reviewing() && b.status === 'reviewed') {
            <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="revise(b)">Correct and resubmit</button>
          }
        </app-page-header>
        @if (!reviewing() && b.status === 'draft') {
          <p class="notice notice-info small">This is exactly what {{ b.university }} will receive: each student's number, name, program, regulation and this term's courses and outcomes.</p>
        }
        <div class="card section table-card">
          <table>
            <thead><tr><th>Student</th><th>Regulation</th><th>Courses</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead>
            <tbody>
              @for (r of b.rows; track r.id) {
                <tr>
                  <td><strong>{{ r.number }}</strong> {{ r.full_name }}{{ r.is_correction ? ' · correction' : '' }}{{ reviewing() && r.current ? ' · current record' : '' }}</td>
                  <td>{{ r.regulation || '—' }}</td>
                  <td class="small">@for (a of r.attempts; track $index) { <span class="course">{{ a.course }} {{ a.outcome }}{{ a.grade_point ? ' ' + a.grade_point : '' }}</span> }</td>
                  <td class="small">
                    @if (r.problems.length) { <span class="field-error">{{ r.problems.join(' ') }}</span> }
                    @else { {{ r.status_label }}{{ r.reason ? ': ' + r.reason : '' }} }
                  </td>
                  <td class="actions">
                    @if (!reviewing() && b.status === 'draft') {
                      <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Remove ' + r.number" [disabled]="busy()" (click)="remove(b, r)">Remove</button>
                    }
                    @if (!reviewing() && b.status === 'reviewed' && r.status === 'accepted') {
                      <label class="small"><input type="checkbox" [id]="'correct-' + r.id" (change)="mark(r.id, $any($event.target).checked)" /> Correct</label>
                    }
                    @if (reviewing() && r.status === 'accepted' && r.current && canAward()) {
                      <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Issue award to ' + r.number" [disabled]="busy()" (click)="award(r)">Issue award</button>
                    }
                    @if (reviewing() && r.status === 'pending' && b.status === 'submitted') {
                      <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Accept ' + r.number" [disabled]="busy()" (click)="decide(b, r, 'accepted')">Accept</button>
                      <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Return ' + r.number" [disabled]="busy()" (click)="decide(b, r, 'rejected')">Return</button>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
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
        padding: 8px;
        text-align: left;
        vertical-align: top;
        border-bottom: 1px solid var(--border);
      }
    }

    .course {
      display: block;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
  `,
})
export class BatchPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  private readonly confirm = inject(ConfirmDialog);
  /** Set by the route: the university's review of a received batch. */
  protected readonly reviewing = signal(!!inject(ActivatedRoute).snapshot.data['review']);
  private base(): string {
    return this.reviewing() ? `institution/affiliations/received/${this.id()}` : `institution/affiliations/batches/${this.id()}`;
  }
  protected readonly data = load(
    () => this.api.get<SubmissionBatch>(this.base()),
    () => this.id(),
  );
  protected readonly blocked = computed(() => (this.data.value()?.rows ?? []).some((r) => r.problems.length));
  private readonly corrections = signal<ReadonlySet<string>>(new Set());
  protected readonly busy = signal(false);

  private run(request: Observable<SubmissionBatch>, message: string, after?: (b: SubmissionBatch) => void): void {
    this.busy.set(true);
    request.subscribe({
      next: (b) => {
        this.busy.set(false);
        this.toasts.show(message);
        if (after) {
          after(b);
        } else {
          this.data.value.set(b);
        }
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  private readonly auth = inject(AuthStore);
  protected readonly canAward = computed(() => this.auth.can('results.publish'));

  protected award(r: BatchRow): void {
    this.busy.set(true);
    this.api.post<{ number: string }>('institution/results/affiliation-awards', { row: r.id }).subscribe({
      next: (doc) => {
        this.busy.set(false);
        this.toasts.show(`Award ${doc.number} issued to ${r.full_name}.`);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected mark(id: string, on: boolean): void {
    this.corrections.update((ids) => {
      const next = new Set(ids);
      if (on) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  }

  protected submit(b: SubmissionBatch): void {
    this.run(this.api.post<SubmissionBatch>(`${this.base()}/submit`, {}), `Sent to ${b.university}.`);
  }

  protected remove(b: SubmissionBatch, r: BatchRow): void {
    this.run(this.api.delete<SubmissionBatch>(`${this.base()}/rows/${r.id}`), `${r.number} removed.`);
  }

  protected revise(b: SubmissionBatch): void {
    this.run(
      this.api.post<SubmissionBatch>(`${this.base()}/revise`, { corrections: [...this.corrections()] }),
      `Revision ${b.revision + 1} drafted.`,
      (made) => this.router.navigate(['/app/affiliations/batches', made.id]),
    );
  }

  protected async decide(b: SubmissionBatch, r: BatchRow, decision: 'accepted' | 'rejected'): Promise<void> {
    let reason = '';
    if (decision === 'rejected') {
      const answer = await this.confirm.prompt({
        title: `Return ${r.number} for correction?`,
        label: 'What needs correcting',
        confirmLabel: 'Return',
        required: true,
      });
      if (!answer) {
        return;
      }
      reason = answer;
    }
    this.run(this.api.post<SubmissionBatch>(`${this.base()}/rows/${r.id}`, { decision, reason }), `${r.number} ${decision}.`);
  }
}
