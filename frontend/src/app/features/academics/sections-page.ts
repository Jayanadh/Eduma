import { Component, inject, signal } from '@angular/core';
import { of } from 'rxjs';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { AcademicYear, Campus, Grade, Page, ClassSection, Program } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { ToastService } from '../../ui/toast';

/** Sections by year and grade (a college's batches by program), and a form to add one. */
@Component({
  selector: 'app-sections-page',
  imports: [EmptyState, LoadError, PageHeader, Pager, RouterLink],
  templateUrl: './sections-page.html',
  styles: `
    .filters,
    .add {
      display: grid;
      gap: 12px;
      align-items: end;

      @media (min-width: 900px) {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    .add {
      @media (min-width: 900px) {
        grid-template-columns: repeat(5, minmax(0, 1fr)) auto;
      }
    }
  `,
})
export class SectionsPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly years = load(() => this.api.get<AcademicYear[]>('institution/academics/years'));
  /** A college's sections are batches of a program; a school's are classes of a grade. */
  protected readonly higher = inject(AuthStore).higher;
  protected readonly grades = load(() => (this.higher() ? of([]) : this.api.get<Grade[]>('institution/academics/grades')));
  protected readonly programs = load(() =>
    this.higher() ? this.api.get<Program[]>('institution/academics/programs') : of([] as Program[]),
  );
  protected readonly campuses = load(() => this.api.get<Page<Campus>>('institution/campuses', { page_size: 200, active: 1 }));
  protected readonly year = signal('');
  protected readonly grade = signal('');
  protected readonly program = signal('');
  protected readonly page = signal(1);
  protected readonly data = load(
    () =>
      this.api.get<Page<ClassSection>>('institution/academics/sections', {
        year: this.year(),
        grade: this.grade(),
        program: this.program(),
        page: this.page(),
      }),
    () => [this.year(), this.grade(), this.program(), this.page()],
  );
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  protected set(target: { set(value: string): void }, value: string): void {
    target.set(value);
    this.page.set(1);
  }

  protected add(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)?.value ?? '';
    const level = this.higher() ? { program: field('new-program') } : { grade: field('new-grade') };
    const body = {
      year: field('new-year'),
      ...level,
      campus: field('new-campus'),
      code: field('new-code').trim(),
      capacity: Number(field('new-capacity')),
    };
    this.busy.set(true);
    this.errors.set({});
    this.api.post<ClassSection>('institution/academics/sections', body).subscribe({
      next: (made) => {
        this.busy.set(false);
        form.reset();
        this.toasts.show(`Section ${made.code} added.`);
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
