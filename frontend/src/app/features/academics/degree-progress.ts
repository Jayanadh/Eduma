import { Component, input } from '@angular/core';
import { DegreeProgress } from '../../core/api/types';

const STATUS: Record<string, string> = {
  completed: 'Completed',
  in_progress: 'In progress',
  failed: 'Failed — to retake',
  planned: 'Planned',
};

/** Advisory degree progress (SCR-029): credits by state, averages and each regulation course. Never an award. */
@Component({
  selector: 'app-degree-progress',
  template: `
    @let p = progress();
    <p class="notice notice-info small">{{ p.note }}</p>
    <div class="figures">
      <div><span class="muted small">CGPA</span><strong>{{ p.cgpa ?? '—' }}</strong></div>
      <div><span class="muted small">Earned</span><strong>{{ p.credits.earned }}</strong></div>
      <div><span class="muted small">Toward this degree</span><strong>{{ p.credits.accepted }} / {{ p.credits.required }}</strong></div>
      <div><span class="muted small">In progress</span><strong>{{ p.credits.in_progress }}</strong></div>
      <div><span class="muted small">Planned</span><strong>{{ p.credits.planned }}</strong></div>
      <div><span class="muted small">Still unmet</span><strong>{{ p.credits.unmet }}</strong></div>
    </div>
    @if (p.regulation) {
      <p class="muted small">{{ p.regulation }} · repeats count by the rule “{{ p.repeat_rule }}”; credits count once.</p>
    }
    @if (p.terms.length) {
      <p class="small">@for (t of p.terms; track $index) { <span class="term">{{ t.year }} {{ t.term }}: SGPA {{ t.sgpa ?? '—' }}</span> }</p>
    }
    <ul class="rows">
      @for (c of p.courses; track c.code) {
        <li>
          <span><strong>{{ c.code }}</strong> {{ c.title }} <span class="muted small">· term {{ c.term }} · {{ c.credits }} credits · {{ c.category }}{{ c.prerequisites_met ? '' : ' · prerequisites not met' }}</span></span>
          <span class="badge" [class.badge-success]="c.status === 'completed'" [class.badge-info]="c.status === 'in_progress'" [class.badge-warning]="c.status === 'failed'">{{ status[c.status] }}</span>
        </li>
      }
    </ul>
    @if (p.attempts.length) {
      <h3 class="card-title">Attempts</h3>
      <ul class="rows">
        @for (a of p.attempts; track a.id) {
          <li>
            <span>{{ a.course }} · attempt {{ a.attempt_no }} <span class="muted small">· {{ a.year }} {{ a.term }}</span></span>
            <span class="small">{{ a.outcome_label }}{{ a.grade_point ? ' · ' + a.grade_point : '' }}</span>
          </li>
        }
      </ul>
    }
  `,
  styles: `
    .figures {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
      gap: 12px;
      margin: 12px 0;

      div {
        display: flex;
        flex-direction: column;
      }

      strong {
        font-size: 1.25rem;
      }
    }

    .term + .term::before {
      content: ' · ';
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
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
    }
  `,
})
export class DegreeProgressView {
  readonly progress = input.required<DegreeProgress>();
  protected readonly status = STATUS;
}
