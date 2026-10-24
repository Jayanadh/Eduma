import { Component, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { CurriculumSummary, Program } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** One program and its regulations: drafts, published and retired. */
@Component({
  selector: 'app-program-page',
  imports: [LoadError, PageHeader, RouterLink],
  templateUrl: './program-page.html',
  styles: `
    .add {
      display: grid;
      gap: 12px;
      align-items: end;

      @media (min-width: 720px) {
        grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
      }
    }
  `,
})
export class ProgramPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  protected readonly program = load(
    () => this.api.get<Program>(`institution/academics/programs/${this.id()}`),
    () => this.id(),
  );
  protected readonly curricula = load(
    () => this.api.get<CurriculumSummary[]>(`institution/academics/programs/${this.id()}/curricula`),
    () => this.id(),
  );
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  protected draft(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)?.value.trim() ?? '';
    const body = { regulation: field('new-regulation'), cohort: Number(field('new-cohort')), credits_required: field('new-credits') };
    this.busy.set(true);
    this.errors.set({});
    this.api.post<CurriculumSummary>(`institution/academics/programs/${this.id()}/curricula`, body).subscribe({
      next: (made) => {
        this.busy.set(false);
        this.router.navigate(['/app/academics/curricula', made.id]);
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
