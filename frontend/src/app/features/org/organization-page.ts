import { Component, inject, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { Campus, Department, Page } from '../../core/api/types';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { Icon } from '../../ui/icon';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { SearchBox } from '../../ui/search-box';
import { StatusBadge } from '../../ui/status-badge';
import { ToastService } from '../../ui/toast';
import { CampusForm } from './campus-form';
import { DepartmentForm } from './department-form';

type Editing = { kind: 'campus'; record: Campus | null } | { kind: 'department'; record: Department | null };
const ALL = { page_size: 200 };

/** Where the institution works: its campuses, and departments that may sit at a campus or under each other. */
@Component({
  selector: 'app-organization-page',
  imports: [CampusForm, DepartmentForm, EmptyState, Icon, LoadError, PageHeader, Pager, SearchBox, StatusBadge],
  template: `
    <div class="page">
      <app-page-header title="Organization" subtitle="Your campuses and departments. Roles can be given for one of them." />

      @if (editing(); as edit) {
        <section class="card card-strong section">
          @if (edit.kind === 'campus') {
            <app-campus-form [campus]="edit.record" (saved)="saved('Campus saved.')" (cancelled)="editing.set(null)" />
          } @else {
            <app-department-form
              [department]="edit.record"
              [campuses]="activeCampuses()"
              [departments]="allDepartments.value()?.results ?? []"
              (saved)="saved('Department saved.')"
              (cancelled)="editing.set(null)"
            />
          }
        </section>
      }

      <section class="section stack">
        <div class="section-head">
          <h2>Campuses</h2>
          <button type="button" class="btn btn-secondary btn-sm" (click)="editing.set({ kind: 'campus', record: null })">
            <app-icon name="plus" [size]="16" /> Add campus
          </button>
        </div>
        <app-search-box id="campus-search" label="Search campuses by code or name" (search)="campusSearch.set($event); campusPage.set(1)" />
        <app-load-error [message]="campuses.error()" (retry)="campuses.reload()" />
        @if (campuses.value(); as result) {
          @if (result.results.length) {
            <div class="card list-card">
              <ul class="list">
                @for (campus of result.results; track campus.id) {
                  <li>
                    <button type="button" class="list-row" (click)="editing.set({ kind: 'campus', record: campus })">
                      <span class="list-main">
                        <span class="list-title">{{ campus.name }}</span>
                        <span class="muted small">{{ campus.code }}{{ campus.address ? ' · ' + campus.address : '' }}</span>
                      </span>
                      <app-status-badge [status]="campus.is_active ? 'active' : 'archived'" [label]="campus.is_active ? 'Active' : 'Inactive'" />
                    </button>
                  </li>
                }
              </ul>
            </div>
            <app-pager [page]="campusPage()" [count]="result.count" (go)="campusPage.set($event)" />
          } @else {
            <app-empty-state icon="search" title="No matching campuses" text="Change the search." />
          }
        }
      </section>

      <section class="section stack">
        <div class="section-head">
          <h2>Departments</h2>
          <button type="button" class="btn btn-secondary btn-sm" (click)="editing.set({ kind: 'department', record: null })">
            <app-icon name="plus" [size]="16" /> Add department
          </button>
        </div>
        <app-search-box id="department-search" label="Search departments by code or name" (search)="departmentSearch.set($event); departmentPage.set(1)" />
        <app-load-error [message]="departments.error()" (retry)="departments.reload()" />
        @if (departments.value(); as result) {
          @if (result.results.length) {
            <div class="card list-card">
              <ul class="list">
                @for (department of result.results; track department.id) {
                  <li>
                    <button type="button" class="list-row" (click)="editing.set({ kind: 'department', record: department })">
                      <span class="list-main">
                        <span class="list-title">{{ department.name }}</span>
                        <span class="muted small">{{ where(department) }}</span>
                      </span>
                      <app-status-badge [status]="department.is_active ? 'active' : 'archived'" [label]="department.is_active ? 'Active' : 'Inactive'" />
                    </button>
                  </li>
                }
              </ul>
            </div>
            <app-pager [page]="departmentPage()" [count]="result.count" (go)="departmentPage.set($event)" />
          } @else if (departmentSearch()) {
            <app-empty-state icon="search" title="No matching departments" text="Change the search." />
          } @else {
            <app-empty-state icon="layers" title="No departments yet" text="Add one, such as Science or Languages." />
          }
        }
      </section>
    </div>
  `,
  styles: `
    .section-head {
      margin-bottom: 0;
    }

    button.list-row {
      width: 100%;
      border-width: 0 0 1px;
      background: none;
      font: inherit;
      text-align: left;
      cursor: pointer;
    }
  `,
})
export class OrganizationPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);

  protected readonly editing = signal<Editing | null>(null);
  protected readonly campusSearch = signal('');
  protected readonly campusPage = signal(1);
  protected readonly departmentSearch = signal('');
  protected readonly departmentPage = signal(1);

  protected readonly campuses = load(
    () => this.api.get<Page<Campus>>('institution/campuses', { search: this.campusSearch(), page: this.campusPage() }),
    () => [this.campusSearch(), this.campusPage()],
  );
  protected readonly departments = load(
    () =>
      this.api.get<Page<Department>>('institution/departments', {
        search: this.departmentSearch(),
        page: this.departmentPage(),
      }),
    () => [this.departmentSearch(), this.departmentPage()],
  );
  /** For the department form's choices. */
  protected readonly allCampuses = load(() => this.api.get<Page<Campus>>('institution/campuses', { ...ALL, active: 1 }));
  protected readonly allDepartments = load(() => this.api.get<Page<Department>>('institution/departments', ALL));

  protected activeCampuses(): Campus[] {
    return this.allCampuses.value()?.results ?? [];
  }

  protected where(department: Department): string {
    const parts = [department.code];
    if (department.parent) {
      parts.push(`part of ${department.parent.name}`);
    }
    if (department.campus) {
      parts.push(department.campus.name);
    }
    return parts.join(' · ');
  }

  protected saved(message: string): void {
    this.editing.set(null);
    this.toasts.show(message);
    for (const list of [this.campuses, this.departments, this.allCampuses, this.allDepartments]) {
      list.reload();
    }
  }
}
