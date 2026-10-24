import { Component, inject, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { Course, Department, Page } from '../../core/api/types';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { SearchBox } from '../../ui/search-box';
import { ToastService } from '../../ui/toast';

const KINDS = [
  ['theory', 'Theory'],
  ['lab', 'Lab'],
  ['tutorial', 'Tutorial'],
  ['project', 'Project'],
  ['other', 'Other'],
];

/** The course catalogue: search it, and add a course. */
@Component({
  selector: 'app-courses-page',
  imports: [EmptyState, LoadError, PageHeader, Pager, SearchBox],
  template: `
    <div class="page">
      <app-page-header eyebrow="Academics" title="Courses" subtitle="Every course the college teaches, with its credits." />
      <app-search-box id="course-search" label="Search courses" (search)="search.set($event); page.set(1)" />
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as result) {
        @if (result.results.length) {
          <div class="card list-card section">
            <ul class="list">
              @for (c of result.results; track c.id) {
                <li>
                  <div class="list-row">
                    <span class="list-main">
                      <span class="list-title">{{ c.code }} · {{ c.title }}</span>
                      <span class="muted small">{{ c.credits }} credits · {{ c.kind_label }}{{ c.department ? ' · ' + c.department.name : '' }}{{ c.is_active ? '' : ' · inactive' }}</span>
                    </span>
                  </div>
                </li>
              }
            </ul>
          </div>
          <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
        } @else {
          <app-empty-state icon="book-open" title="No courses" [text]="search() ? 'Nothing matches that search.' : 'Add the first course below.'" />
        }
      }
      <form id="add-course" class="card stack section" (submit)="$event.preventDefault(); add($any($event.target))">
        <h2 class="card-title">Add a course</h2>
        <div class="add">
          <div class="field">
            <label for="new-code">Code</label>
            <input id="new-code" placeholder="PHY101" />
            @if (errors()['code']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field">
            <label for="new-title">Title</label>
            <input id="new-title" placeholder="Mechanics" />
            @if (errors()['title']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field">
            <label for="new-credits">Credits</label>
            <input id="new-credits" type="number" min="0" max="30" step="0.5" value="4" />
            @if (errors()['credits']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field">
            <label for="new-kind">Kind</label>
            <select id="new-kind">
              @for (k of kinds; track k[0]) { <option [value]="k[0]">{{ k[1] }}</option> }
            </select>
          </div>
          <div class="field">
            <label for="new-department">Department</label>
            <select id="new-department">
              <option value="">Whole institution</option>
              @for (d of departments.value()?.results ?? []; track d.id) { @if (d.is_active) { <option [value]="d.id">{{ d.name }}</option> } }
            </select>
            @if (errors()['department']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Add course</button>
        </div>
      </form>
    </div>
  `,
  styles: `
    .add {
      display: grid;
      gap: 12px;
      align-items: end;

      @media (min-width: 900px) {
        grid-template-columns: repeat(5, minmax(0, 1fr)) auto;
      }
    }
  `,
})
export class CoursesPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly kinds = KINDS;
  protected readonly search = signal('');
  protected readonly page = signal(1);
  protected readonly data = load(
    () => this.api.get<Page<Course>>('institution/academics/courses', { search: this.search(), page: this.page() }),
    () => [this.search(), this.page()],
  );
  protected readonly departments = load(() => this.api.get<Page<Department>>('institution/departments', { page_size: 200 }));
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  protected add(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)?.value.trim() ?? '';
    const body = {
      code: field('new-code'),
      title: field('new-title'),
      credits: field('new-credits'),
      kind: field('new-kind'),
      department: field('new-department') || null,
    };
    this.busy.set(true);
    this.errors.set({});
    this.api.post<Course>('institution/academics/courses', body).subscribe({
      next: (made) => {
        this.busy.set(false);
        form.reset();
        this.toasts.show(`Course ${made.code} added.`);
        this.data.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.errors.set(fieldErrors(err));
        if (!Object.keys(fieldErrors(err)).length) {
          this.toasts.show(apiErrorMessage(err), 'danger');
        }
      },
    });
  }
}
