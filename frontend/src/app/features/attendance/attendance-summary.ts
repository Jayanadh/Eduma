import { Component, input } from '@angular/core';
import { AttendanceSummary } from '../../core/api/types';
import { date } from '../../core/format';

/** Attendance so far: counted sessions only — unmarked days are not absences and excused days don't count. */
@Component({
  selector: 'app-attendance-summary',
  template: `
    @let s = summary();
    <p class="small">
      <strong>{{ s.percentage === null ? 'No attendance yet' : s.percentage + '%' }}</strong>
      @if (s.counted) { <span class="muted"> · present {{ s.present }}, late {{ s.late }}, absent {{ s.absent }}{{ s.excused ? ', excused ' + s.excused : '' }} of {{ s.counted }} counted</span> }
    </p>
    @if (s.absences.length) {
      <ul class="plain small">
        @for (a of s.absences; track $index) { <li>Absent {{ date(a.date) }} · {{ a.label }}</li> }
      </ul>
    }
  `,
  styles: `
    .plain {
      margin: 6px 0 0;
      padding-left: 18px;
    }
  `,
})
export class AttendanceSummaryView {
  readonly summary = input.required<AttendanceSummary>();
  protected readonly date = date;
}
