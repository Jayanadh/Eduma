import { booleanAttribute, Component, inject, input, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { AuditItem, Page } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { Pager } from '../../ui/pager';
import { SearchBox } from '../../ui/search-box';

const ACTIONS = [
  { prefix: '', label: 'Everything' },
  { prefix: 'auth.', label: 'Sign-ins and passwords' },
  { prefix: 'institution.', label: 'Institutions' },
  { prefix: 'site.', label: 'Public pages' },
  { prefix: 'membership.', label: 'Admin logins' },
];

/** Audit events, newest first: the whole platform's (with filters) or one institution's. */
@Component({
  selector: 'app-audit-list',
  imports: [EmptyState, LoadError, Pager, SearchBox],
  template: `
    @if (filters()) {
      <div class="filters">
        <app-search-box id="audit-search" label="Search what happened or who did it" (search)="search.set($event); page.set(1)" />
        <div class="field">
          <label for="audit-action">Kind of event</label>
          <select id="audit-action" (change)="action.set($any($event.target).value); page.set(1)">
            @for (option of actions; track option.prefix) {
              <option [value]="option.prefix">{{ option.label }}</option>
            }
          </select>
        </div>
      </div>
    }
    <app-load-error [message]="data.error()" (retry)="data.reload()" />
    @if (data.value(); as result) {
      @if (result.results.length) {
        <div class="card">
          <div class="table-wrap" role="region" aria-label="Audit events" tabindex="0">
            <table class="table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Who</th>
                  @if (filters()) {
                    <th scope="col">Institution</th>
                  }
                  <th scope="col">What happened</th>
                </tr>
              </thead>
              <tbody>
                @for (event of result.results; track event.id) {
                  <tr>
                    <td class="nowrap">{{ dateTime(event.at) }}</td>
                    <td>{{ event.actor_name ?? 'System' }}</td>
                    @if (filters()) {
                      <td>{{ event.institution_name ?? '—' }}</td>
                    }
                    <td>
                      {{ event.summary }}
                      <span class="muted small action">{{ event.action }}</span>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </div>
        <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
      } @else {
        <app-empty-state icon="list" title="No events" text="Nothing recorded matches yet." />
      }
    } @else if (data.loading()) {
      <p class="muted" role="status">Loading…</p>
    }
  `,
  styles: `
    :host {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .filters {
      display: grid;
      gap: 12px;

      @media (min-width: 900px) {
        grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
        align-items: end;
      }
    }

    .action {
      display: block;
    }
  `,
})
export class AuditList {
  /** The list's address under /api/v1/, e.g. platform/audit or platform/institutions/<id>/audit. */
  readonly path = input.required<string>();
  readonly filters = input(false, { transform: booleanAttribute });
  private readonly api = inject(Api);

  protected readonly actions = ACTIONS;
  protected readonly search = signal('');
  protected readonly action = signal('');
  protected readonly page = signal(1);
  protected readonly dateTime = dateTime;
  protected readonly data = load(
    () =>
      this.api.get<Page<AuditItem>>(this.path(), {
        search: this.search(),
        action: this.action(),
        page: this.page(),
      }),
    () => [this.path(), this.search(), this.action(), this.page()],
  );
}
