import { Component, inject } from '@angular/core';
import { Api } from '../../core/api/api';
import { of } from 'rxjs';
import { AttendanceSummary, OwnStudentRecord } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { AttendanceSummaryView } from '../attendance/attendance-summary';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PortalFrame } from '../apply/portal-frame';

/** A student's own home: their number and where they are enrolled. Timetables, results and fees join it module by
 * module. */
@Component({
  selector: 'app-student-home',
  imports: [AttendanceSummaryView, LoadError, PortalFrame],
  template: `
    <app-portal-frame heading="Your record">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as me) {
        <section class="card">
          <p class="muted small">Student number</p>
          <p class="number">{{ me.number }}</p>
          <p>{{ me.full_name }}</p>
          @if (me.current_section) {
            <p class="small"><strong>{{ me.current_section }}</strong></p>
          }
          @if (me.enrollment; as now) {
            <p class="small">
              {{ now.place_label }} · {{ now.academic_year }}{{ now.campus_name ? ' · ' + now.campus_name : '' }}
              <span class="muted">· since {{ date(now.entry_date) }}</span>
            </p>
          }
        </section>
        @if (attendance.value(); as summary) {
          <section class="card"><h2 class="card-title">Attendance</h2><app-attendance-summary [summary]="summary" /></section>
        }
        <p class="notice notice-info">More arrives here with each module your school switches on.</p>
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </app-portal-frame>
  `,
  styles: `
    .number {
      margin: 4px 0 8px;
      font-size: 28px;
      font-weight: 800;
      letter-spacing: 0.02em;
    }
  `,
})
export class StudentHome {
  private readonly api = inject(Api);
  private readonly auth = inject(AuthStore);
  protected readonly date = date;
  protected readonly data = load(() => this.api.get<OwnStudentRecord>('student/me'));
  protected readonly attendance = load(() =>
    (this.auth.user()?.membership?.modules_enabled?.includes('attendance') ?? false) ? this.api.get<AttendanceSummary>('student/attendance') : of(null),
  );
}
