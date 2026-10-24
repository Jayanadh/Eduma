import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { AcademicYear, Campus, Course, Offering, Page } from '../../core/api/types';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { SearchBox } from '../../ui/search-box';
import { ToastService } from '../../ui/toast';

const NONE = { count: 0, next: null, previous: null, results: [] };

/** Each term's course offerings, and a form to offer a course (a lab linked to its lecture). */
@Component({
  selector: 'app-offerings-page',
  imports: [EmptyState, LoadError, PageHeader, Pager, RouterLink, SearchBox],
  template: `
    <div class="page">
      <app-page-header eyebrow="Academics" title="Offerings" subtitle="The courses taught each term, with their seats and teachers." />
      <div class="field section">
        <label for="filter-term">Term</label>
        <select id="filter-term" (change)="term.set($any($event.target).value); page.set(1)">
          <option value="">All terms</option>
          @for (t of terms(); track t.id) { <option [value]="t.id">{{ t.label }}</option> }
        </select>
      </div>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as result) {
        @if (result.results.length) {
          <div class="card list-card section">
            <ul class="list">
              @for (o of result.results; track o.id) {
                <li>
                  <a class="list-row" [routerLink]="['/app/academics/offerings', o.id]">
                    <span class="list-main">
                      <span class="list-title">{{ o.label }} · {{ o.course.title }}</span>
                      <span class="muted small">{{ o.term.year }} {{ o.term.name }} · {{ o.campus.name }} · {{ o.capacity }} seats{{ o.linked_to ? ' · with ' + o.linked_to.label : '' }}</span>
                    </span>
                    <span class="badge badge-info">{{ o.status_label }}</span>
                  </a>
                </li>
              }
            </ul>
          </div>
          <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
        } @else {
          <app-empty-state icon="clipboard" title="No offerings" text="Offer a course for a term below." />
        }
      }
      <form id="add-offering" class="card stack section" (submit)="$event.preventDefault(); add($any($event.target))">
        <h2 class="card-title">Offer a course</h2>
        @if (chosen(); as picked) {
          <ul class="chips">
            <li class="chip">{{ picked.label }} <button type="button" class="btn-icon" [attr.aria-label]="'Remove ' + picked.label" (click)="chosen.set(null)">×</button></li>
          </ul>
        } @else {
          <app-search-box id="offer-search" label="Find the course" (search)="search.set($event)" />
          <ul class="choices">
            @for (c of found.value()?.results ?? []; track c.id) {
              <li>
                <span>{{ c.code }} {{ c.title }}</span>
                <button type="button" class="btn btn-secondary btn-sm" (click)="choose(c.id, c.code + ' ' + c.title)">Choose</button>
              </li>
            }
          </ul>
          @if (errors()['course']; as m) { <span class="field-error">{{ m }}</span> }
        }
        <div class="add">
          <div class="field">
            <label for="new-term">Term</label>
            <select id="new-term" (change)="newTerm.set($any($event.target).value)">
              <option value="">Choose a term</option>
              @for (t of terms(); track t.id) { @if (t.open) { <option [value]="t.id">{{ t.label }}</option> } }
            </select>
            @if (errors()['term']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field">
            <label for="new-campus">Campus</label>
            <select id="new-campus">
              @for (c of campuses.value()?.results ?? []; track c.id) { <option [value]="c.id">{{ c.name }}</option> }
            </select>
            @if (errors()['campus']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field">
            <label for="new-code">Section</label>
            <input id="new-code" placeholder="A" />
            @if (errors()['code']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field">
            <label for="new-capacity">Seats</label>
            <input id="new-capacity" type="number" min="1" value="60" />
            @if (errors()['capacity']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field">
            <label for="new-link">Goes with</label>
            <select id="new-link">
              <option value="">Nothing</option>
              @for (o of linkable.value()?.results ?? []; track o.id) { <option [value]="o.id">{{ o.label }}</option> }
            </select>
            @if (errors()['linked_to']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy() || !chosen()">Offer</button>
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

    .choices {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;

      li {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
    }
  `,
})
export class OfferingsPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly years = load(() => this.api.get<AcademicYear[]>('institution/academics/years'));
  protected readonly terms = computed(() =>
    (this.years.value() ?? []).flatMap((y) =>
      y.terms.map((t) => ({ id: t.id, label: `${y.code} · ${t.name}`, open: y.status !== 'closed' })),
    ),
  );
  protected readonly campuses = load(() => this.api.get<Page<Campus>>('institution/campuses', { page_size: 200, active: 1 }));
  protected readonly term = signal('');
  protected readonly page = signal(1);
  protected readonly data = load(
    () => this.api.get<Page<Offering>>('institution/academics/offerings', { term: this.term(), page: this.page() }),
    () => [this.term(), this.page()],
  );
  protected readonly search = signal('');
  protected readonly found = load(
    () =>
      this.search().length >= 3
        ? this.api.get<Page<Course>>('institution/academics/courses', { search: this.search() })
        : of({ ...NONE, results: [] as Course[] }),
    () => this.search(),
  );
  protected readonly chosen = signal<{ id: string; label: string } | null>(null);
  protected readonly newTerm = signal('');
  /** What the new offering may go with: the offerings of its term. */
  protected readonly linkable = load(
    () =>
      this.newTerm()
        ? this.api.get<Page<Offering>>('institution/academics/offerings', { term: this.newTerm(), page_size: 200 })
        : of({ ...NONE, results: [] as Offering[] }),
    () => this.newTerm(),
  );
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  protected choose(id: string, label: string): void {
    this.chosen.set({ id, label });
  }

  protected add(form: HTMLFormElement): void {
    const chosen = this.chosen();
    if (!chosen) {
      return;
    }
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)?.value.trim() ?? '';
    const body = {
      course: chosen.id,
      term: this.newTerm(),
      campus: field('new-campus'),
      code: field('new-code'),
      capacity: Number(field('new-capacity')),
      linked_to: field('new-link') || null,
    };
    this.busy.set(true);
    this.errors.set({});
    this.api.post<Offering>('institution/academics/offerings', body).subscribe({
      next: (made) => {
        this.busy.set(false);
        this.toasts.show(`${made.label} offered.`);
        this.chosen.set(null);
        this.data.reload();
        this.linkable.reload();
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
