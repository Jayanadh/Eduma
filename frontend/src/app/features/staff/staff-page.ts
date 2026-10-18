import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { Page, StaffItem } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { Icon } from '../../ui/icon';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { SearchBox } from '../../ui/search-box';
import { StatusBadge } from '../../ui/status-badge';

/** The staff the signed-in member may see, with their roles: search as you type, open one. */
@Component({
  selector: 'app-staff-page',
  imports: [EmptyState, Icon, LoadError, PageHeader, Pager, RouterLink, SearchBox, StatusBadge],
  template: `
    <div class="page">
      <app-page-header title="Staff" subtitle="Who works here and what each person may do.">
        @if (auth.can('membership.assign')) {
          <a class="btn btn-primary" routerLink="/app/staff/new"><app-icon name="user-plus" [size]="18" /> Add staff</a>
        }
      </app-page-header>
      <div class="section">
        <app-search-box id="staff-search" label="Search by name or login ID" (search)="search.set($event); page.set(1)" />
      </div>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as result) {
        @if (result.results.length) {
          <div class="card list-card section">
            <ul class="list">
              @for (person of result.results; track person.id) {
                <li>
                  <a class="list-row" [routerLink]="['/app/staff', person.id]">
                    <span class="list-main">
                      <span class="list-title">{{ person.full_name }}</span>
                      <span class="muted small">{{ person.username }}</span>
                      <span class="chips roles">
                        @for (role of person.roles; track $index) {
                          <span class="chip">{{ role.label }} · {{ role.scope_label }}</span>
                        } @empty {
                          <span class="muted small">No role</span>
                        }
                      </span>
                    </span>
                    @if (person.status === 'revoked') {
                      <app-status-badge status="archived" label="Removed" />
                    }
                  </a>
                </li>
              }
            </ul>
          </div>
          <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
        } @else if (search()) {
          <app-empty-state icon="search" title="No matching staff" text="Change the search." />
        } @else {
          <app-empty-state icon="users" title="No staff to show" text="People you can see will appear here." />
        }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .roles {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 6px;
    }
  `,
})
export class StaffPage {
  private readonly api = inject(Api);
  protected readonly auth = inject(AuthStore);
  protected readonly search = signal('');
  protected readonly page = signal(1);
  protected readonly data = load(
    () => this.api.get<Page<StaffItem>>('institution/staff', { search: this.search(), page: this.page() }),
    () => [this.search(), this.page()],
  );
}
