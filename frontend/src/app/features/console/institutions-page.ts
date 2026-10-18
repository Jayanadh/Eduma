import { Component, inject, input, linkedSignal, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { CATEGORY_LABELS, InstitutionListItem, Page } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { CopyUrl } from '../../ui/copy-url';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { SearchBox } from '../../ui/search-box';
import { StatusBadge } from '../../ui/status-badge';

/** Every institution on Eduma: search as you type, filter by category and state, open one. */
@Component({
  selector: 'app-institutions-page',
  imports: [CopyUrl, EmptyState, LoadError, PageHeader, Pager, RouterLink, SearchBox, StatusBadge],
  template: `
    <div class="page">
      <app-page-header eyebrow="Eduma platform" title="Institutions">
        <a class="btn btn-primary" routerLink="/console/institutions/new">Add institution</a>
      </app-page-header>

      <div class="filters section">
        <app-search-box id="institution-search" label="Search by name or address" (search)="filter(search, $event)" />
        <div class="field">
          <label for="filter-category">Category</label>
          <select id="filter-category" (change)="filter(category, $any($event.target).value)">
            <option value="">All categories</option>
            @for (option of categories; track option[0]) {
              <option [value]="option[0]" [selected]="option[0] === category()">{{ option[1] }}</option>
            }
          </select>
        </div>
        <div class="field">
          <label for="filter-status">State</label>
          <select id="filter-status" (change)="filter(status, $any($event.target).value)">
            <option value="">All states</option>
            <option value="setup" [selected]="status() === 'setup'">Setting up</option>
            <option value="active" [selected]="status() === 'active'">Active</option>
            <option value="restricted" [selected]="status() === 'restricted'">Restricted</option>
            <option value="suspended" [selected]="status() === 'suspended'">Suspended</option>
            <option value="archived" [selected]="status() === 'archived'">Archived</option>
          </select>
        </div>
      </div>

      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as result) {
        <p class="muted small count" role="status">
          {{ result.count }} {{ result.count === 1 ? 'institution' : 'institutions' }}
        </p>
        @if (result.results.length) {
          <div class="card list-card">
            <ul class="list">
              @for (item of result.results; track item.id) {
                <li class="row-item">
                  <a class="list-row" [routerLink]="['/console/institutions', item.id]">
                    <span class="list-main">
                      <span class="list-title">{{ item.display_name }}</span>
                      <span class="muted small">{{ categoryLabel(item.category) }} · added {{ date(item.created_at) }}</span>
                    </span>
                    <app-status-badge [status]="item.lifecycle_status" />
                    @if (item.lifecycle_status === 'setup') {
                      <span [class]="item.ready ? 'badge badge-success' : 'badge badge-warning'">
                        {{ item.ready ? 'Ready to activate' : 'Setup incomplete' }}
                      </span>
                    }
                  </a>
                  <app-copy-url class="row-url" [url]="item.url" />
                </li>
              }
            </ul>
          </div>
          <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
        } @else if (search() || category() || status()) {
          <app-empty-state icon="search" title="No matching institutions" text="Change the search or filters." />
        } @else {
          <app-empty-state icon="institution" title="No institutions yet" text="Add the first one to give it its Eduma address." />
        }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .filters {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 12px;

      @media (min-width: 900px) {
        grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr);
        align-items: end;
      }
    }

    .count {
      margin: 16px 0 8px;
    }

    .row-item {
      padding: 0 0 12px;
      border-bottom: 1px solid var(--border);

      &:last-child {
        padding-bottom: 0;
        border-bottom: 0;
      }

      .list-row {
        flex-wrap: wrap;
        padding-bottom: 6px;
        border-bottom: 0;
      }
    }

    .list .row-item:not(:first-child) {
      padding-top: 12px;
    }

    .row-url {
      color: var(--muted);
    }
  `,
})
export class InstitutionsPage {
  /** ?status= from a link on the overview. */
  readonly initialStatus = input<string | undefined>('', { alias: 'status' });
  private readonly api = inject(Api);

  protected readonly categories = Object.entries(CATEGORY_LABELS);
  protected readonly search = signal('');
  protected readonly category = signal('');
  // The router sets a missing ?status to undefined.
  protected readonly status = linkedSignal(() => this.initialStatus() ?? '');
  protected readonly page = signal(1);
  protected readonly date = date;

  protected readonly data = load(
    () =>
      this.api.get<Page<InstitutionListItem>>('platform/institutions', {
        search: this.search(),
        category: this.category(),
        status: this.status(),
        page: this.page(),
      }),
    () => [this.search(), this.category(), this.status(), this.page()],
  );

  /** A new search or filter starts again from the first page. */
  protected filter(target: { set(value: string): void }, value: string): void {
    target.set(value);
    this.page.set(1);
  }

  protected categoryLabel(code: InstitutionListItem['category']): string {
    return CATEGORY_LABELS[code];
  }
}
