import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { Department, Page, Program } from '../../core/api/types';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** A college's programs, and a form to add one. */
@Component({
  selector: 'app-programs-page',
  imports: [EmptyState, LoadError, PageHeader, RouterLink],
  templateUrl: './programs-page.html',
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
export class ProgramsPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly programs = load(() => this.api.get<Program[]>('institution/academics/programs'));
  protected readonly departments = load(() => this.api.get<Page<Department>>('institution/departments', { page_size: 200 }));
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  protected add(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)?.value.trim() ?? '';
    const body = {
      code: field('new-code'),
      name: field('new-name'),
      qualification: field('new-qualification'),
      length_terms: Number(field('new-length')),
      department: field('new-department') || null,
    };
    this.busy.set(true);
    this.errors.set({});
    this.api.post<Program>('institution/academics/programs', body).subscribe({
      next: (made) => {
        this.busy.set(false);
        form.reset();
        this.toasts.show(`Program ${made.code} added.`);
        this.programs.reload();
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
