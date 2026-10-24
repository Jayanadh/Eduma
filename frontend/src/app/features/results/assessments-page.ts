import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AcademicYear, AssessmentT, ClassSection, Offering, Page, SchemeT, Subject } from '../../core/api/types';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** Assessments (S7-02): set one up for a class and subject, or an offering; marks are entered on its page. */
@Component({
  selector: 'app-assessments-page',
  imports: [EmptyState, LoadError, PageHeader, RouterLink],
  template: `
    <div class="page">
      <app-page-header eyebrow="Results" title="Assessments" subtitle="Marks entered by teachers, moderated, then published as results." />
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as rows) {
        @if (rows.length) {
          <div class="card list-card section">
            <ul class="list">
              @for (a of rows; track a.id) {
                <li><a class="list-row" [routerLink]="['/app/results/assessments', a.id]">
                  <span class="list-main"><span class="list-title">{{ a.title }}</span><span class="muted small">{{ a.target.label }}{{ a.subject ? ' · ' + a.subject : '' }} · {{ a.term.name }}</span></span>
                  <span class="badge badge-info">{{ a.state_label }}</span>
                </a></li>
              }
            </ul>
          </div>
        } @else {
          <app-empty-state icon="clipboard" title="No assessments" text="Set one up below." />
        }
      }
      <form id="add-assessment" class="card stack section" (submit)="$event.preventDefault(); add($any($event.target))">
        <h2 class="card-title">New assessment</h2>
        <div class="grid">
          <div class="field"><label for="a-title">Title</label><input id="a-title" placeholder="Science term test" /></div>
          <div class="field"><label for="a-scheme">Scheme</label>
            <select id="a-scheme">@for (s of published(); track s.id) { <option [value]="s.id">{{ s.name }} (rev {{ s.revision }})</option> }</select></div>
          <div class="field"><label for="a-term">Term</label>
            <select id="a-term">@for (t of terms(); track t.id) { <option [value]="t.id">{{ t.label }}</option> }</select></div>
          <div class="field"><label for="a-class">Class</label>
            <select id="a-class">
              @for (s of sections.value()?.results ?? []; track s.id) { <option [value]="'section:' + s.id">{{ s.code }} · {{ s.level }}</option> }
              @for (o of offerings.value()?.results ?? []; track o.id) { <option [value]="'offering:' + o.id">{{ o.label }} · {{ o.course.title }}</option> }
            </select></div>
          <div class="field"><label for="a-subject">Subject (classes)</label>
            <select id="a-subject"><option value="">—</option>@for (s of subjects.value() ?? []; track s.id) { <option [value]="s.id">{{ s.name }}</option> }</select></div>
        </div>
        <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Set up</button></div>
      </form>
    </div>
  `,
  styles: `
    .grid {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    }
  `,
})
export class AssessmentsPage {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  protected readonly data = load(() => this.api.get<AssessmentT[]>('institution/results/assessments'));
  private readonly schemes = load(() => this.api.get<SchemeT[]>('institution/results/schemes'));
  protected readonly published = computed(() => (this.schemes.value() ?? []).filter((s) => s.status === 'published'));
  private readonly years = load(() => this.api.get<AcademicYear[]>('institution/academics/years'));
  protected readonly terms = computed(() =>
    (this.years.value() ?? []).filter((y) => y.status !== 'closed').flatMap((y) => y.terms.map((t) => ({ id: t.id, label: `${y.code} ${t.name}` }))),
  );
  protected readonly sections = load(() => this.api.get<Page<ClassSection>>('institution/academics/sections', { page_size: 200 }));
  protected readonly offerings = load(() => this.api.get<Page<Offering>>('institution/academics/offerings', { page_size: 200 }));
  protected readonly subjects = load(() => this.api.get<Subject[]>('institution/academics/subjects'));
  protected readonly busy = signal(false);

  protected add(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
    const [kind, id] = field('a-class').split(':');
    const body = { title: field('a-title'), scheme: field('a-scheme'), term: field('a-term'), [kind]: id, subject: field('a-subject') || null };
    this.busy.set(true);
    this.api.post<AssessmentT>('institution/results/assessments', body).subscribe({
      next: (made) => {
        this.busy.set(false);
        this.router.navigate(['/app/results/assessments', made.id]);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
