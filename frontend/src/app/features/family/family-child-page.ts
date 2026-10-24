import { Component, inject, input } from '@angular/core';
import { Api } from '../../core/api/api';
import { FamilyChild } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PortalFrame } from '../apply/portal-frame';
import { ChildSummary } from './child-summary';
import { catchError, of } from 'rxjs';
import { AttendanceSummary } from '../../core/api/types';
import { AttendanceSummaryView } from '../attendance/attendance-summary';

/** One child, as their guardian may see them. Attendance, results and fees join this page module by module. */
@Component({
  selector: 'app-family-child-page',
  imports: [AttendanceSummaryView, ChildSummary, LoadError, PortalFrame],
  template: `
    <app-portal-frame [heading]="data.value()?.full_name ?? 'Your child'">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as child) {
        <section class="card"><app-child-summary [child]="child" /></section>
        @if (child.shared) {
          @if (attendance.value(); as summary) {
            <section class="card"><h2 class="card-title">Attendance</h2><app-attendance-summary [summary]="summary" /></section>
          }
          <p class="notice notice-info">More arrives here with each module your school switches on.</p>
        }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </app-portal-frame>
  `,
})
export class FamilyChildPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  protected readonly data = load(
    () => this.api.get<FamilyChild>(`family/children/${this.id()}`),
    () => this.id(),
  );
  // Shown only when the record is shared and Attendance is on; otherwise the server answers 404 and nothing shows.
  protected readonly attendance = load(
    () => this.api.get<AttendanceSummary>(`family/children/${this.id()}/attendance`).pipe(catchError(() => of(null))),
    () => this.id(),
  );
}
