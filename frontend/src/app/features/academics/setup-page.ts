import { Component, inject, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { AcademicYear, Grade, Subject } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

const BASE = 'institution/academics';

/** The school's year structure: academic years and their terms, grades and subjects (SCR-021). */
@Component({
  selector: 'app-setup-page',
  imports: [LoadError, PageHeader],
  templateUrl: './setup-page.html',
  styleUrl: './setup-page.scss',
})
export class SetupPage {
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly years = load(() => this.api.get<AcademicYear[]>(`${BASE}/years`));
  protected readonly grades = load(() => this.api.get<Grade[]>(`${BASE}/grades`));
  protected readonly subjects = load(() => this.api.get<Subject[]>(`${BASE}/subjects`));
  protected readonly busy = signal(false);
  /** Field errors by form: "year", "term-<year id>", "grade", "subject". */
  protected readonly errors = signal<Record<string, Record<string, string>>>({});

  protected problem(form: string, field: string): string {
    return this.errors()[form]?.[field] ?? '';
  }

  private value(form: HTMLFormElement, id: string): string {
    return form.querySelector<HTMLInputElement>(`#${id}`)?.value.trim() ?? '';
  }

  private send<T>(form: string, request: Observable<T>, message: string, after: () => void, element?: HTMLFormElement): void {
    this.busy.set(true);
    this.errors.update((all) => ({ ...all, [form]: {} }));
    request.subscribe({
      next: () => {
        this.busy.set(false);
        element?.reset();
        this.toasts.show(message);
        after();
      },
      error: (err) => {
        this.busy.set(false);
        const fields = fieldErrors(err);
        this.errors.update((all) => ({ ...all, [form]: fields }));
        if (!Object.keys(fields).length) {
          this.toasts.show(apiErrorMessage(err), 'danger');
        }
      },
    });
  }

  protected addYear(form: HTMLFormElement): void {
    const body = {
      code: this.value(form, 'year-code'),
      starts_on: this.value(form, 'year-start'),
      ends_on: this.value(form, 'year-end'),
    };
    this.send('year', this.api.post(`${BASE}/years`, body), `${body.code} added.`, () => this.years.reload(), form);
  }

  protected setStatus(year: AcademicYear, status: string): void {
    this.send(
      `status-${year.id}`,
      this.api.patch(`${BASE}/years/${year.id}`, { version: year.version, status }),
      `${year.code} is now ${status}.`,
      () => this.years.reload(),
    );
  }

  protected addTerm(year: AcademicYear, form: HTMLFormElement): void {
    const body = {
      name: this.value(form, `term-name-${year.id}`),
      ordinal: year.terms.length + 1,
      starts_on: this.value(form, `term-start-${year.id}`),
      ends_on: this.value(form, `term-end-${year.id}`),
    };
    this.send(`term-${year.id}`, this.api.post(`${BASE}/years/${year.id}/terms`, body), 'Term added.', () => this.years.reload(), form);
  }

  protected addGrade(form: HTMLFormElement): void {
    const order = (this.grades.value() ?? []).length + 1;
    const body = { code: this.value(form, 'grade-code'), name: this.value(form, 'grade-name'), order };
    this.send('grade', this.api.post(`${BASE}/grades`, body), `${body.name} added.`, () => this.grades.reload(), form);
  }

  protected addSubject(form: HTMLFormElement): void {
    const body = { code: this.value(form, 'subject-code'), name: this.value(form, 'subject-name') };
    this.send('subject', this.api.post(`${BASE}/subjects`, body), `${body.name} added.`, () => this.subjects.reload(), form);
  }

  protected async rename(kind: 'grades' | 'subjects', row: Grade | Subject): Promise<void> {
    const name = await this.confirm.prompt({
      title: `Rename ${row.name}`,
      label: 'Name',
      value: row.name,
      required: true,
      confirmLabel: 'Rename',
    });
    if (name === null || name === row.name) {
      return;
    }
    const reload = () => (kind === 'grades' ? this.grades.reload() : this.subjects.reload());
    this.send(kind, this.api.patch(`${BASE}/${kind}/${row.id}`, { version: row.version, name }), 'Renamed.', reload);
  }
}
