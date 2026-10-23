import { Component, input } from '@angular/core';
import { FamilyChild } from '../../core/api/types';
import { date } from '../../core/format';

/** Name, number and class when shared; a neutral line when not. */
@Component({
  selector: 'app-child-summary',
  template: `
    <h2 class="card-title">{{ child().full_name }}</h2>
    @if (child().shared) {
      <p class="small">Student number <strong>{{ child().number }}</strong></p>
      @if (child().current_section) {
        <p class="small">Class <strong>{{ child().current_section }}</strong></p>
      }
      @if (child().enrollment; as e) {
        <p class="small">
          {{ e.place_label }} · {{ e.academic_year }}{{ e.campus_name ? ' · ' + e.campus_name : '' }}
        </p>
      }
      @if (child().left_on) {
        <p class="small"><strong>Left on {{ date(child().left_on) }}</strong></p>
      }
    } @else {
      <p class="muted small">Your school has not shared this record with you.</p>
    }
  `,
})
export class ChildSummary {
  readonly child = input.required<FamilyChild>();
  protected readonly date = date;
}
