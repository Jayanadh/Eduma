import { Component, computed, inject, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { StatusBadge } from '../../ui/status-badge';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AuthStore } from '../../core/auth-store';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { EvidenceT, InternshipT, ROW_STYLES, ScholarT } from './types';

/** Any staff member's share of institutional development: interns and scholars they supervise, evidence they owe. */
@Component({
  selector: 'app-supervision-page',
  imports: [PageHeader, StatusBadge],
  template: `
    <div class="page">
      <app-page-header eyebrow="Academics" title="Supervision and evidence" subtitle="Interns and scholars you supervise, and evidence asked of you." />
      @if (placements()) {
        <section class="card stack section">
          <h2 class="card-title">Interns</h2>
          <ul class="rows">
            @for (i of interns.value() ?? []; track i.id) {
              <li>
                <span>{{ i.student.name }} <span class="muted small meta">{{ i.opportunity }}, {{ i.employer }}{{ i.score ? ' · scored ' + i.score : '' }}</span></span>
                <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Evaluate ' + i.student.name" (click)="evaluate(i)">Evaluate</button>
              </li>
            } @empty {
              <li class="muted small">No interns.</li>
            }
          </ul>
        </section>
      }
      @if (quality()) {
        <section class="card stack section">
          <h2 class="card-title">Scholars</h2>
          @for (s of scholars.value() ?? []; track s.id) {
            <h3 class="small"><strong>{{ s.student.name }}</strong> · {{ s.topic }}</h3>
            <ul class="rows">
              @for (m of s.milestones; track m.id) {
                <li>
                  <span>{{ m.title }} <app-status-badge [status]="m.state" /><span class="muted small meta">due {{ date(m.due_on) }}{{ m.summary ? ' · ' + m.summary : '' }}</span></span>
                  @if (m.state === 'submitted') {
                    <span class="actions">
                      <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve ' + m.title" (click)="decide(m.id, 'approve')">Approve</button>
                      <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Return ' + m.title" (click)="decide(m.id, 'return')">Return</button>
                    </span>
                  }
                </li>
              }
            </ul>
          } @empty {
            <p class="muted small">No scholars.</p>
          }
        </section>
        <section class="card stack section">
          <h2 class="card-title">Evidence asked of you</h2>
          <ul class="rows">
            @for (r of evidence.value() ?? []; track r.id) {
              <li>
                <span><strong>{{ r.criterion }}</strong> {{ r.title }} <app-status-badge [status]="r.state" /><span class="muted small meta">{{ r.cycle.framework }} {{ r.cycle.period }}{{ r.note ? ' · ' + r.note : '' }}</span></span>
                @if (r.state === 'requested' || r.state === 'returned') {
                  <label class="btn btn-secondary btn-sm">Upload (PDF, PNG or JPEG)
                    <input type="file" class="sr-only" [attr.data-request]="r.id" accept=".pdf,.png,.jpg,.jpeg" (change)="upload(r, $any($event.target))" />
                  </label>
                }
              </li>
            } @empty {
              <li class="muted small">Nothing asked of you.</li>
            }
          </ul>
        </section>
      }
    </div>
  `,
  styles: [ROW_STYLES],
})
export class SupervisionPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly dialog = inject(ConfirmDialog);
  private readonly auth = inject(AuthStore);
  protected readonly date = date;
  protected readonly placements = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('placements') ?? false);
  protected readonly quality = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('quality') ?? false);
  protected readonly interns = load(() => (this.placements() ? this.api.get<InternshipT[]>('development/internships') : of([])));
  protected readonly scholars = load(() => (this.quality() ? this.api.get<ScholarT[]>('development/scholars') : of([])));
  protected readonly evidence = load(() => (this.quality() ? this.api.get<EvidenceT[]>('development/evidence') : of([])));
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        this.interns.reload();
        this.scholars.reload();
        this.evidence.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected async evaluate(i: InternshipT): Promise<void> {
    const score = await this.dialog.prompt({ title: `Evaluate ${i.student.name}`, label: 'Score out of 100', confirmLabel: 'Next', required: true });
    const remarks = score && (await this.dialog.prompt({ title: `Evaluate ${i.student.name}`, label: 'Remarks', type: 'textarea', confirmLabel: 'Save' }));
    if (score && remarks !== null) {
      this.run(this.api.post(`development/internships/${i.id}/evaluate`, { score, remarks }), 'Evaluation saved.');
    }
  }

  protected async decide(id: string, action: 'approve' | 'return'): Promise<void> {
    const note = action === 'return' ? await this.dialog.prompt({ title: 'Return the milestone', label: 'What needs more work', confirmLabel: 'Return', required: true }) : '';
    if (note !== null) {
      this.run(this.api.post(`development/milestones/${id}/${action}`, { note }), action === 'approve' ? 'Approved.' : 'Returned.');
    }
  }

  protected upload(r: EvidenceT, input: HTMLInputElement): void {
    const file = input.files?.[0];
    if (file) {
      this.run(this.api.upload(`development/evidence/${r.id}/upload`, 'file', file), `${file.name} uploaded.`);
    }
    input.value = '';
  }
}
