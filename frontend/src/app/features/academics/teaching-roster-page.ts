import { Component, computed, inject, input } from '@angular/core';
import { Api } from '../../core/api/api';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ClassTools } from '../attendance/class-tools';
import { AuthStore } from '../../core/auth-store';

/** Who is in a class a teacher teaches: number, name and status only. */
@Component({
  selector: 'app-teaching-roster-page',
  imports: [ClassTools, LoadError, PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="My classes" title="Class list" backLink="/app/teaching" />
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as rows) {
        <div class="card list-card section">
          <ul class="list">
            @for (row of rows; track row.number) {
              <li class="list-row">
                <span class="list-main"><span class="list-title">{{ row.number }} · {{ row.full_name }}</span></span>
                @if (row.status !== 'active') { <span class="badge">{{ row.status }}</span> }
              </li>
            } @empty {
              <li class="list-row muted small">Nobody placed in this class yet.</li>
            }
          </ul>
        </div>
        @if (attendanceOn()) { <app-class-tools kind="section" [target]="id()" /> }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
})
export class TeachingRosterPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly auth = inject(AuthStore);
  protected readonly attendanceOn = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('attendance') ?? false);
  protected readonly data = load(
    () => this.api.get<{ number: string; full_name: string; status: string }[]>(`teaching/classes/${this.id()}/students`),
    () => this.id(),
  );
}
