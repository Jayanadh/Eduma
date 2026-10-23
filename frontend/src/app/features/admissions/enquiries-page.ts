import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { EnquiryPageResult, EnquiryStatus } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { SearchBox } from '../../ui/search-box';

export const ENQUIRY_STATUSES: [EnquiryStatus, string][] = [
  ['open', 'Open'],
  ['following_up', 'Following up'],
  ['converted', 'Applied'],
  ['closed', 'Closed'],
];
export const ENQUIRY_SOURCES: [string, string][] = [
  ['website', 'Website'],
  ['walk_in', 'Walk-in'],
  ['phone', 'Phone'],
  ['referral', 'Referral'],
  ['event', 'Event'],
  ['other', 'Other'],
];

/** Questions from families: counts by status, filters, and each enquiry to open. */
@Component({
  selector: 'app-enquiries-page',
  imports: [EmptyState, LoadError, PageHeader, Pager, RouterLink, SearchBox],
  template: `
    <div class="page">
      <app-page-header eyebrow="Admissions" title="Enquiries">
        <a class="btn btn-primary" routerLink="/app/admissions/enquiries/new">New enquiry</a>
      </app-page-header>
      @if (data.value(); as result) {
        <ul class="counts section" aria-label="Enquiries by status">
          @for (s of statuses; track s[0]) {
            <li><strong>{{ s[1] }} {{ result.summary.status[s[0]] ?? 0 }}</strong></li>
          }
        </ul>
      }
      <div class="filters section">
        <app-search-box id="enquiry-search" label="Search by number, name or phone" (search)="set(search, $event)" />
        <div class="field">
          <label for="enquiry-status">Status</label>
          <select id="enquiry-status" (change)="set(status, $any($event.target).value)">
            <option value="">All</option>
            @for (s of statuses; track s[0]) { <option [value]="s[0]">{{ s[1] }}</option> }
          </select>
        </div>
        <div class="field">
          <label for="enquiry-source">Came from</label>
          <select id="enquiry-source" (change)="set(source, $any($event.target).value)">
            <option value="">Anywhere</option>
            @for (s of sources; track s[0]) { <option [value]="s[0]">{{ s[1] }}</option> }
          </select>
        </div>
        <div class="checks">
          <label><input id="enquiry-mine" type="checkbox" (change)="set(mine, $any($event.target).checked ? 'me' : '')" /> Assigned to me</label>
          <label><input id="enquiry-due" type="checkbox" (change)="set(due, $any($event.target).checked ? '1' : '')" /> Follow-up due</label>
        </div>
      </div>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as result) {
        @if (result.results.length) {
          <div class="card list-card section">
            <ul class="list">
              @for (item of result.results; track item.id) {
                <li>
                  <a class="list-row" [routerLink]="['/app/admissions/enquiries', item.id]">
                    <span class="list-main">
                      <span class="list-title">{{ item.number }} · {{ item.contact_name }}{{ item.learner_name ? ' for ' + item.learner_name : '' }}</span>
                      <span class="muted small">
                        {{ item.source_label }}{{ item.place ? ' · ' + item.place.label : '' }}
                        · {{ item.assigned_to ? item.assigned_to.full_name : 'Not assigned' }}
                        @if (item.next_follow_up_on) { · follow up {{ date(item.next_follow_up_on) }} }
                      </span>
                    </span>
                    <span class="badge badge-info">{{ item.status_label }}</span>
                  </a>
                </li>
              }
            </ul>
          </div>
          <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
        } @else {
          <app-empty-state icon="file-text" title="No enquiries" text="Questions from the Apply page and the ones you record appear here." />
        }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .counts {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 20px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .filters {
      display: grid;
      gap: 12px;

      @media (min-width: 900px) {
        grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr) auto;
        align-items: end;
      }
    }

    .checks {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      padding-bottom: 10px;
    }
  `,
})
export class EnquiriesPage {
  private readonly api = inject(Api);
  protected readonly statuses = ENQUIRY_STATUSES;
  protected readonly sources = ENQUIRY_SOURCES;
  protected readonly date = date;
  protected readonly search = signal('');
  protected readonly status = signal('');
  protected readonly source = signal('');
  protected readonly mine = signal('');
  protected readonly due = signal('');
  protected readonly page = signal(1);
  protected readonly data = load(
    () =>
      this.api.get<EnquiryPageResult>('institution/admissions/enquiries', {
        search: this.search(),
        status: this.status(),
        source: this.source(),
        assigned: this.mine(),
        due: this.due(),
        page: this.page(),
      }),
    () => [this.search(), this.status(), this.source(), this.mine(), this.due(), this.page()],
  );

  protected set(target: { set(value: string): void }, value: string): void {
    target.set(value);
    this.page.set(1);
  }
}
