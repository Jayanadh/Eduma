import { Component, inject, signal } from '@angular/core';
import { of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

type ReportInfo = { key: string; title: string; columns: string[]; can_export: boolean };
type ReportResult = {
  key: string;
  title: string;
  columns: string[];
  rows: (string | number)[][];
  provenance: { generated_at: string; source: string; scope: string; row_count: number };
};
type ExportT = { id: string; report: string; title: string; state: string; rows: number | null; error: string; created_at: string; expires_at: string | null };

/** Reports the viewer may run, with where the numbers came from (S11-01), and their exports (S11-03). */
@Component({
  selector: 'app-reports-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Administration" title="Reports" subtitle="Each report shows only the records you may read." />
      <app-load-error [message]="list.error()" (retry)="list.reload()" />
      <div class="chips section">
        @for (r of list.value() ?? []; track r.key) {
          <button type="button" class="btn btn-sm" [class.btn-primary]="open() === r.key" [class.btn-secondary]="open() !== r.key" (click)="open.set(r.key)">{{ r.title }}</button>
        } @empty {
          <p class="muted small">No reports for your roles and the modules switched on.</p>
        }
      </div>
      <app-load-error [message]="result.error()" (retry)="result.reload()" />
      @if (result.value(); as r) {
        <section class="card stack section">
          <div class="head">
            <h2 class="card-title">{{ r.title }}</h2>
            @if (canExport(r.key)) { <button type="button" id="export" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="export(r.key)">Export CSV</button> }
          </div>
          <p class="muted small">{{ r.provenance.source }} · {{ r.provenance.scope }} · {{ r.provenance.row_count }} rows · as of {{ dateTime(r.provenance.generated_at) }}</p>
          <div class="table-wrap">
            <table>
              <thead><tr>@for (c of r.columns; track c) { <th scope="col">{{ c }}</th> }</tr></thead>
              <tbody>
                @for (row of r.rows; track $index) { <tr>@for (cell of row; track $index) { <td>{{ cell }}</td> }</tr> }
                @empty { <tr><td [attr.colspan]="r.columns.length" class="muted">Nothing to report.</td></tr> }
              </tbody>
            </table>
          </div>
        </section>
      }
      @if ((exports.value() ?? []).length) {
        <section class="card stack section">
          <div class="head"><h2 class="card-title">Your exports</h2><button type="button" class="btn btn-secondary btn-sm" (click)="exports.reload()">Refresh</button></div>
          <ul class="rows">
            @for (e of exports.value() ?? []; track e.id) {
              <li>
                <span>{{ e.title }} <span class="muted small">· {{ dateTime(e.created_at) }} · {{ e.state }}{{ e.rows !== null ? ' · ' + e.rows + ' rows' : '' }}{{ e.error ? ' · ' + e.error : '' }}</span></span>
                @if (e.state === 'done') { <a class="btn btn-secondary btn-sm" [href]="'/api/v1/institution/reports/exports/' + e.id + '/file'" download>Download</a> }
              </li>
            }
          </ul>
          <p class="muted small">Exports are kept for 7 days. A waiting export is built by the next worker pass.</p>
        </section>
      }
    </div>
  `,
  styles: `
    .chips,
    .head {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
    }

    .chips {
      justify-content: flex-start;
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    th,
    td {
      padding: 6px 8px;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }

    .rows {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;

      li {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        gap: 8px;
      }
    }
  `,
})
export class ReportsPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly dateTime = dateTime;
  protected readonly open = signal('');
  protected readonly list = load(() => this.api.get<ReportInfo[]>('institution/reports/'));
  protected readonly result = load(
    () => (this.open() ? this.api.get<ReportResult>(`institution/reports/${this.open()}`) : of(null)),
    () => this.open(),
  );
  protected readonly exports = load(() => this.api.get<ExportT[]>('institution/reports/exports'));
  protected readonly busy = signal(false);

  protected canExport(key: string): boolean {
    return (this.list.value() ?? []).some((r) => r.key === key && r.can_export);
  }

  protected export(key: string): void {
    this.busy.set(true);
    this.api.post(`institution/reports/${key}/exports`, {}).subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show('Export requested; it will be ready shortly.');
        this.exports.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
