import { LowerCasePipe } from '@angular/common';
import { Component, computed, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { Course, Curriculum, CurriculumEntry, Page } from '../../core/api/types';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { SearchBox } from '../../ui/search-box';
import { ToastService } from '../../ui/toast';

const CATEGORIES = [
  ['core', 'Core'],
  ['elective', 'Elective'],
  ['open_elective', 'Open elective'],
  ['lab', 'Lab'],
  ['project', 'Project'],
];

/** One regulation: its courses term by term. A draft is edited and published; a published one only revised. */
@Component({
  selector: 'app-curriculum-page',
  imports: [LoadError, LowerCasePipe, PageHeader, SearchBox],
  templateUrl: './curriculum-page.html',
  styleUrl: './section-page.scss', // the same rows and chips as a section's
})
export class CurriculumPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  private readonly confirm = inject(ConfirmDialog);
  protected readonly categories = CATEGORIES;
  private base(): string {
    return `institution/academics/curricula/${this.id()}`;
  }
  protected readonly data = load(
    () => this.api.get<Curriculum>(this.base()),
    () => this.id(),
  );
  protected readonly editable = computed(() => this.data.value()?.status === 'draft' && !!this.data.value()?.can_manage);
  protected readonly entries = computed(() => (this.data.value()?.terms ?? []).flatMap((t) => t.courses));
  protected readonly termNumbers = computed(() =>
    Array.from({ length: this.data.value()?.program.length_terms ?? 0 }, (_, i) => i + 1),
  );
  protected readonly search = signal('');
  protected readonly found = load(
    () =>
      this.search().length >= 3
        ? this.api.get<Page<Course>>('institution/academics/courses', { search: this.search() })
        : of({ count: 0, next: null, previous: null, results: [] as Course[] }),
    () => this.search(),
  );
  protected readonly chosen = signal<{ id: string; label: string } | null>(null);
  protected readonly category = signal('core');
  protected readonly term = signal(1);
  protected readonly needs = signal<ReadonlySet<string>>(new Set());
  protected readonly busy = signal(false);

  protected choose(id: string, label: string): void {
    this.chosen.set({ id, label });
  }

  protected toggle(courseId: string, on: boolean): void {
    this.needs.update((ids) => {
      const next = new Set(ids);
      if (on) {
        next.add(courseId);
      } else {
        next.delete(courseId);
      }
      return next;
    });
  }

  private run(request: Observable<Curriculum>, message: string, after: (result: Curriculum) => void = () => undefined): void {
    this.busy.set(true);
    request.subscribe({
      next: (result) => {
        this.busy.set(false);
        this.data.value.set(result);
        this.toasts.show(message);
        after(result);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected add(form: HTMLFormElement): void {
    const chosen = this.chosen();
    if (!chosen) {
      return;
    }
    const body = {
      course: chosen.id,
      category: this.category(),
      term: this.term(),
      elective_group: form.querySelector<HTMLInputElement>('#add-group')?.value.trim() ?? '',
      prerequisites: [...this.needs()],
    };
    this.run(this.api.post<Curriculum>(`${this.base()}/courses`, body), `${chosen.label} added.`, () => {
      form.reset();
      // The selects are back on their first options; keep what is sent in step with them.
      this.chosen.set(null);
      this.needs.set(new Set());
      this.category.set('core');
      this.term.set(1);
      this.search.set('');
    });
  }

  protected async remove(entry: CurriculumEntry): Promise<void> {
    const yes = await this.confirm.ask({
      title: `Remove ${entry.course.code}?`,
      message: 'It comes out of this draft regulation.',
      confirmLabel: 'Remove',
    });
    if (yes) {
      this.run(this.api.delete<Curriculum>(`${this.base()}/courses/${entry.id}`), `${entry.course.code} removed.`);
    }
  }

  protected async publish(c: Curriculum): Promise<void> {
    const yes = await this.confirm.ask({
      title: `Publish ${c.regulation} rev ${c.revision}?`,
      message: 'A published regulation never changes. Students are pinned to it; a change is a new revision.',
      confirmLabel: 'Publish',
    });
    if (yes) {
      this.run(this.api.post<Curriculum>(`${this.base()}/publish`, { version: c.version }), 'Published.');
    }
  }

  protected async retire(c: Curriculum): Promise<void> {
    const yes = await this.confirm.ask({
      title: `Retire ${c.regulation} rev ${c.revision}?`,
      message: 'Students already pinned to it keep it; nobody new is pinned to it.',
      confirmLabel: 'Retire',
    });
    if (yes) {
      this.run(this.api.post<Curriculum>(`${this.base()}/retire`, { version: c.version }), 'Retired.');
    }
  }

  protected revise(c: Curriculum): void {
    this.busy.set(true);
    this.api.post<Curriculum>(`${this.base()}/revise`, { version: c.version }).subscribe({
      next: (made) => {
        this.busy.set(false);
        this.toasts.show(`Revision ${made.revision} drafted.`);
        this.router.navigate(['/app/academics/curricula', made.id]);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
