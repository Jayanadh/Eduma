import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { Page, StudentListItem } from '../../core/api/types';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { SearchBox } from '../../ui/search-box';

/** Students the viewer's roles cover: search by number or name, open a record. */
@Component({
  selector: 'app-students-page',
  imports: [EmptyState, LoadError, PageHeader, Pager, RouterLink, SearchBox],
  template: `
    <div class="page">
      <app-page-header eyebrow="People" title="Students" subtitle="Students join here when an accepted application is enrolled." />
      <div class="filters section">
        <app-search-box id="student-search" label="Search by number or name" (search)="search.set($event); page.set(1)" />
        <div class="field">
          <label for="student-status">Status</label>
          <select id="student-status" (change)="status.set($any($event.target).value); page.set(1)">
            <option value="">All</option>
            <option value="active">Active</option>
            <option value="withdrawn">Withdrawn</option>
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
                  <a class="list-row" [routerLink]="['/app/students', item.id]">
                    <span class="list-main">
                      <span class="list-title">{{ item.number }} · {{ item.full_name }}</span>
                      @if (item.enrollment; as now) {
                        <span class="muted small">{{ now.place_label }} · {{ now.academic_year }}{{ now.campus_name ? ' · ' + now.campus_name : '' }}</span>
                      }
                    </span>
                    <span class="badge badge-info">{{ item.status }}</span>
                  </a>
                </li>
              }
            </ul>
          </div>
          <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
        } @else {
          <app-empty-state icon="graduation" title="No students" text="Enrolled applicants appear here with their student number." />
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
        grid-template-columns: minmax(0, 3fr) minmax(0, 1fr);
        align-items: end;
      }
    }
  `,
})
export class StudentsPage {
  private readonly api = inject(Api);
  protected readonly search = signal('');
  protected readonly status = signal('');
  protected readonly page = signal(1);
  protected readonly data = load(
    () =>
      this.api.get<Page<StudentListItem>>('institution/students', {
        search: this.search(),
        status: this.status(),
        page: this.page(),
      }),
    () => [this.search(), this.status(), this.page()],
  );
}
