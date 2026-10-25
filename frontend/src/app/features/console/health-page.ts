import { Component, inject } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { StatusBadge } from '../../ui/status-badge';
import { ToastService } from '../../ui/toast';

type Tile = { key: string; label: string; status: string; value: string; threshold: string; source: string; runbook: string; observed_at: string };
type AlertT = { id: string; key: string; severity: string; summary: string; runbook: string; state: string; opened_at: string; last_seen_at: string; owner: string | null };
type Run = { task: string; status: string; detail: string; started_at: string };
type BackupsT = { backups: { taken_at: string; size_bytes: number }[]; drills: { ran_at: string; seconds: string; passed: boolean; detail: { tables: number; rows: number } }[] };

/** Platform health (SCR-008): each signal with its age and threshold; unknown is grey, never green. */
@Component({
  selector: 'app-health-page',
  imports: [LoadError, PageHeader, StatusBadge],
  template: `
    <div class="page">
      <app-page-header eyebrow="Eduma platform" title="Health" subtitle="No secrets, hostnames or student data appear here.">
        <button type="button" class="btn btn-secondary" (click)="reload()">Refresh</button>
      </app-page-header>
      <app-load-error [message]="health.error()" (retry)="health.reload()" />
      @if (health.value(); as h) {
        @for (a of h.alerts; track a.id) {
          <div class="card stack section alert" role="alert">
            <span class="headline"><app-status-badge [status]="a.state" /><strong>{{ a.summary }}</strong></span>
            <span class="muted small">{{ a.severity }} · since {{ dateTime(a.opened_at) }} · last seen {{ dateTime(a.last_seen_at) }}{{ a.owner ? ' · owner ' + a.owner : '' }} · runbook {{ a.runbook }}</span>
            @if (a.state === 'open') { <div><button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Acknowledge ' + a.summary" (click)="acknowledge(a)">Acknowledge</button></div> }
          </div>
        }
        <div class="card section">
          <table>
            <thead><tr><th scope="col">Service</th><th scope="col">Status</th><th scope="col">Reading</th><th scope="col">Expected</th><th scope="col">Observed</th></tr></thead>
            <tbody>
              @for (t of h.tiles; track t.key) {
                <tr><td>{{ t.label }}</td><td><app-status-badge [status]="t.status" /></td><td>{{ t.value }}</td><td class="muted">{{ t.threshold }}</td><td class="muted small">{{ dateTime(t.observed_at) }}</td></tr>
              }
            </tbody>
          </table>
        </div>
      }
      <section class="card stack section">
        <h2 class="card-title">Backups and restore drills</h2>
        <ul class="rows">
          @for (d of backups.value()?.drills ?? []; track d.ran_at) {
            <li>Drill {{ dateTime(d.ran_at) }} · {{ d.passed ? 'passed' : 'FAILED' }} · {{ d.seconds }} s · {{ d.detail.tables }} tables, {{ d.detail.rows }} rows</li>
          }
          @for (b of backups.value()?.backups ?? []; track b.taken_at) {
            <li>Backup {{ dateTime(b.taken_at) }} · {{ (b.size_bytes / 1048576).toFixed(1) }} MB</li>
          } @empty {
            <li class="muted small">No backups recorded.</li>
          }
        </ul>
      </section>
      <section class="card stack section">
        <h2 class="card-title">Recent jobs</h2>
        <ul class="rows">
          @for (r of jobs.value() ?? []; track $index) { <li class="small">{{ dateTime(r.started_at) }} · {{ r.task }} · {{ r.status }} · {{ r.detail }}</li> }
          @empty { <li class="muted small">The worker hasn't run yet.</li> }
        </ul>
      </section>
    </div>
  `,
  styles: `
    table {
      width: 100%;
      border-collapse: collapse;
    }

    th,
    td {
      padding: 8px;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }

    .headline {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }

    .alert {
      border-left: 4px solid var(--danger, #b42318);
    }

    .rows {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
  `,
})
export class HealthPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly dateTime = dateTime;
  protected readonly health = load(() => this.api.get<{ tiles: Tile[]; alerts: AlertT[] }>('platform/health'));
  protected readonly backups = load(() => this.api.get<BackupsT>('platform/backups'));
  protected readonly jobs = load(() => this.api.get<Run[]>('platform/jobs'));

  protected reload(): void {
    this.health.reload();
    this.backups.reload();
    this.jobs.reload();
  }

  protected acknowledge(a: AlertT): void {
    this.api.post(`platform/alerts/${a.id}/acknowledge`, {}).subscribe({
      next: () => {
        this.toasts.show('Acknowledged; you own it now.');
        this.health.reload();
      },
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }
}
