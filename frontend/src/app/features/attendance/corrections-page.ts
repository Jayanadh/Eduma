import { Component, inject, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AttendanceCorrectionT } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** Attendance corrections waiting for approval (S6-09); approving keeps the original mark on record. */
@Component({
  selector: 'app-corrections-page',
  imports: [EmptyState, LoadError, PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Attendance" title="Corrections" subtitle="Changes to submitted attendance, waiting for someone other than the requester." />
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as rows) {
        @if (rows.length) {
          <div class="card list-card section">
            <ul class="list">
              @for (c of rows; track c.id) {
                <li class="list-row row">
                  <span class="list-main">
                    <span class="list-title">{{ c.student.number }} · {{ c.student.full_name }} · {{ c.label }} {{ date(c.date) }}</span>
                    <span class="muted small">{{ c.previous_code }} → {{ c.new_code }} · {{ c.reason }} · asked by {{ c.requested_by }}</span>
                  </span>
                  <span class="actions">
                    <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve ' + c.student.number" [disabled]="busy()" (click)="decide(c, 'approve')">Approve</button>
                    <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Reject ' + c.student.number" [disabled]="busy()" (click)="decide(c, 'reject')">Reject</button>
                  </span>
                </li>
              }
            </ul>
          </div>
        } @else {
          <app-empty-state icon="check" title="Nothing waiting" text="Corrections teachers ask for appear here." />
        }
      }
    </div>
  `,
  styles: `
    .row {
      flex-wrap: wrap;
    }

    .actions {
      display: flex;
      gap: 8px;
    }
  `,
})
export class CorrectionsPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly data = load(() => this.api.get<AttendanceCorrectionT[]>('institution/attendance/corrections'));
  protected readonly busy = signal(false);

  protected decide(c: AttendanceCorrectionT, action: 'approve' | 'reject'): void {
    this.busy.set(true);
    this.api.post(`institution/attendance/corrections/${c.id}/${action}`, {}).subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(action === 'approve' ? 'Correction approved.' : 'Correction rejected.');
        this.data.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
