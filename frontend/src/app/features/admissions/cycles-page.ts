import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { AdmissionCycle, Page } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { Icon } from '../../ui/icon';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';

const STATUS: Record<AdmissionCycle['status'], [string, string]> = {
  draft: ['Draft', 'badge-info'],
  published: ['Open', 'badge-success'],
  closed: ['Closed', 'badge-muted'],
};

/** Admission cycles: their dates, places and how full each place is. */
@Component({
  selector: 'app-cycles-page',
  imports: [EmptyState, Icon, LoadError, PageHeader, Pager, RouterLink],
  template: `
    <div class="page">
      <app-page-header eyebrow="Admissions" title="Cycles" subtitle="Each cycle opens places for one academic year.">
        @if (auth.can('admission_cycle.manage')) {
          <a class="btn btn-primary" routerLink="/app/admissions/cycles/new"><app-icon name="plus" [size]="18" /> New cycle</a>
        }
      </app-page-header>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as result) {
        @if (result.results.length) {
          <div class="stack section">
            @for (cycle of result.results; track cycle.id) {
              <a class="card stack cycle" [routerLink]="['/app/admissions/cycles', cycle.id]">
                <div class="head">
                  <h2 class="card-title">{{ cycle.name }}</h2>
                  <span [class]="'badge ' + status[cycle.status][1]">{{ status[cycle.status][0] }}</span>
                </div>
                <p class="muted small">For {{ cycle.academic_year }} · {{ date(cycle.opens_on) }} – {{ date(cycle.closes_on) }}</p>
                <ul class="chips">
                  @for (place of cycle.places; track place.code) {
                    <li class="chip">{{ place.label }}: {{ place.in_use }} of {{ place.seats }} taken</li>
                  }
                </ul>
              </a>
            }
          </div>
          <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
        } @else {
          <app-empty-state icon="calendar" title="No cycles yet" text="Create one to open applications." />
        }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .cycle {
      color: inherit;
      text-decoration: none;
    }

    .head {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 12px;
    }
  `,
})
export class CyclesPage {
  private readonly api = inject(Api);
  protected readonly auth = inject(AuthStore);
  protected readonly date = date;
  protected readonly status = STATUS;
  protected readonly page = signal(1);
  protected readonly data = load(
    () => this.api.get<Page<AdmissionCycle>>('institution/admissions/cycles', { page: this.page() }),
    () => this.page(),
  );
}
