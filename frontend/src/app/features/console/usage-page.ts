import { Component, inject } from '@angular/core';
import { Api } from '../../core/api/api';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';

type UsageT = {
  institution: { id: string; name: string; slug: string };
  members: Record<string, number>;
  active_students: number;
  exports_this_month: number;
  messages_this_month: number;
  open_cases: number;
  storage_bytes: number;
};

/** Usage per institution (SCR-009, read only): plans and quotas are not built. */
@Component({
  selector: 'app-usage-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Eduma platform" title="Usage" subtitle="Counts as of now. Plans, quotas and billing are not part of this release." />
      <app-load-error [message]="usage.error()" (retry)="usage.reload()" />
      <div class="card section table-wrap">
        <table>
          <thead><tr><th scope="col">Institution</th><th scope="col">Staff</th><th scope="col">Students</th><th scope="col">Guardians</th><th scope="col">Applicants</th><th scope="col">Exports this month</th><th scope="col">Messages this month</th><th scope="col">Open cases</th><th scope="col">Private storage</th></tr></thead>
          <tbody>
            @for (u of usage.value() ?? []; track u.institution.id) {
              <tr>
                <td>{{ u.institution.name }}</td><td>{{ u.members['staff'] ?? 0 }}</td><td>{{ u.active_students }}</td>
                <td>{{ u.members['guardian'] ?? 0 }}</td><td>{{ u.members['applicant'] ?? 0 }}</td><td>{{ u.exports_this_month }}</td>
                <td>{{ u.messages_this_month }}</td><td>{{ u.open_cases }}</td><td>{{ (u.storage_bytes / 1048576).toFixed(1) }} MB</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </div>
  `,
  styles: `
    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    th,
    td {
      padding: 8px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      white-space: nowrap;
    }
  `,
})
export class UsagePage {
  private readonly api = inject(Api);
  protected readonly usage = load(() => this.api.get<UsageT[]>('platform/usage'));
}
