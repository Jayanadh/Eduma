import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { AdmissionCycle, Page, StaffApplicationItem } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { SearchBox } from '../../ui/search-box';

const STAGES: [string, string][] = [
  ['', 'All stages'],
  ['submitted', 'Submitted'],
  ['under_review', 'Under review'],
  ['needs_information', 'More information needed'],
  ['eligible', 'Eligible'],
  ['offered', 'Place offered'],
  ['accepted', 'Offer accepted'],
  ['enrolled', 'Enrolled'],
  ['rejected', 'Not offered a place'],
  ['offer_expired', 'Offer expired'],
  ['withdrawn', 'Withdrawn'],
];

/** Submitted applications the viewer may review: filter by cycle and stage, search, open one. */
@Component({
  selector: 'app-staff-applications-page',
  imports: [EmptyState, LoadError, PageHeader, Pager, RouterLink, SearchBox],
  template: `
    <div class="page">
      <app-page-header eyebrow="Admissions" title="Applications" />
      <div class="filters section">
        <app-search-box id="application-search" label="Search by number, learner or parent" (search)="filter(search, $event)" />
        <div class="field">
          <label for="filter-cycle">Cycle</label>
          <select id="filter-cycle" (change)="filter(cycle, $any($event.target).value)">
            <option value="">All cycles</option>
            @for (c of cycles.value()?.results ?? []; track c.id) {
              <option [value]="c.id">{{ c.name }}</option>
            }
          </select>
        </div>
        <div class="field">
          <label for="filter-stage">Stage</label>
          <select id="filter-stage" (change)="filter(stage, $any($event.target).value)">
            @for (s of stages; track s[0]) {
              <option [value]="s[0]">{{ s[1] }}</option>
            }
          </select>
        </div>
      </div>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as result) {
        @if (result.results.length) {
          <div class="card list-card section">
            <ul class="list">
              @for (item of result.results; track item.id) {
                <li>
                  <a class="list-row" [routerLink]="['/app/admissions/applications', item.id]">
                    <span class="list-main">
                      <span class="list-title">{{ item.number }} · {{ item.learner_name }}</span>
                      <span class="muted small">{{ item.place }} · {{ item.cycle }} · parent {{ item.guardian_name }} · sent {{ dateTime(item.submitted_at) }}</span>
                    </span>
                    <span class="badge badge-info">{{ item.stage_label }}</span>
                  </a>
                </li>
              }
            </ul>
          </div>
          <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
        } @else {
          <app-empty-state icon="file-text" title="No applications" text="Submitted applications you may review appear here." />
        }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .filters {
      display: grid;
      gap: 12px;

      @media (min-width: 900px) {
        grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr);
        align-items: end;
      }
    }
  `,
})
export class StaffApplicationsPage {
  private readonly api = inject(Api);
  protected readonly stages = STAGES;
  protected readonly dateTime = dateTime;
  protected readonly search = signal('');
  protected readonly cycle = signal('');
  protected readonly stage = signal('');
  protected readonly page = signal(1);
  protected readonly cycles = load(() =>
    this.api.get<Page<AdmissionCycle>>('institution/admissions/cycles', { page_size: 200 }),
  );
  protected readonly data = load(
    () =>
      this.api.get<Page<StaffApplicationItem>>('institution/admissions/applications', {
        search: this.search(),
        cycle: this.cycle(),
        stage: this.stage(),
        page: this.page(),
      }),
    () => [this.search(), this.cycle(), this.stage(), this.page()],
  );

  protected filter(target: { set(value: string): void }, value: string): void {
    target.set(value);
    this.page.set(1);
  }
}
