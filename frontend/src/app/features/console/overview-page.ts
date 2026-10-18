import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { LifecycleStatus, Overview } from '../../core/api/types';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { PAGE_SIZE, Pager } from '../../ui/pager';

const STATES: { code: LifecycleStatus; label: string }[] = [
  { code: 'setup', label: 'Setting up' },
  { code: 'active', label: 'Active' },
  { code: 'restricted', label: 'Restricted' },
  { code: 'suspended', label: 'Suspended' },
  { code: 'archived', label: 'Archived' },
];

/** The console's first page: how many institutions are in each state, and which ones still need setting up. */
@Component({
  selector: 'app-overview-page',
  imports: [EmptyState, LoadError, PageHeader, Pager, RouterLink],
  template: `
    <div class="page">
      <app-page-header eyebrow="Eduma platform" title="Overview">
        <a class="btn btn-primary" routerLink="/console/institutions/new">Add institution</a>
      </app-page-header>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as overview) {
        <div class="grid-4 section">
          @for (state of states; track state.code) {
            <a class="card card-strong figure tile" routerLink="/console/institutions" [queryParams]="{ status: state.code }">
              <strong>{{ overview.counts[state.code] }}</strong>
              <span>{{ state.label }}</span>
            </a>
          }
        </div>
        <section class="section card">
          <div class="section-head"><h2>Needs action</h2></div>
          @if (overview.needs_action.length) {
            <ul class="list">
              @for (item of needsAction(); track item.id) {
                <li>
                  <a class="list-row" [routerLink]="['/console/institutions', item.id]">
                    <span class="list-main">
                      <span class="list-title">{{ item.display_name }}</span>
                      <span class="muted small missing">{{ item.missing.length ? 'Not done yet: ' + item.missing.join('; ') : 'Ready to activate' }}</span>
                    </span>
                  </a>
                </li>
              }
            </ul>
            <app-pager [page]="page()" [count]="overview.needs_action.length" (go)="page.set($event)" />
          } @else {
            <app-empty-state icon="check" title="Nothing needs action." text="Every institution being set up is ready." />
          }
        </section>
      } @else if (data.loading()) {
        <p class="muted section" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .tile {
      color: inherit;
      text-decoration: none;
    }

    .missing {
      display: block;
      margin-top: 2px;
    }
  `,
})
export class OverviewPage {
  private readonly api = inject(Api);
  protected readonly states = STATES;
  protected readonly data = load(() => this.api.get<Overview>('platform/overview'));
  protected readonly page = signal(1);
  /** Few institutions are ever being set up at once, so they come in one answer and are paged here. */
  protected readonly needsAction = computed(() =>
    (this.data.value()?.needs_action ?? []).slice((this.page() - 1) * PAGE_SIZE, this.page() * PAGE_SIZE),
  );
}
