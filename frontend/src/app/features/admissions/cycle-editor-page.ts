import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { AdmissionCycle, Campus, CycleDocument, CycleQuestion, Page, QuestionKind } from '../../core/api/types';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Icon } from '../../ui/icon';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

type PlaceRow = { code: string; label: string; campus: string; seats: number; in_use?: number };
const KINDS: [QuestionKind, string][] = [
  ['text', 'Short answer'],
  ['long_text', 'Long answer'],
  ['date', 'Date'],
  ['choice', 'Choice'],
  ['yes_no', 'Yes or no'],
];

function iso(day: Date): string {
  return day.toISOString().slice(0, 10);
}

/** A cycle's details, places, questions and documents. Editable while a draft; opening it freezes the form. */
@Component({
  selector: 'app-cycle-editor-page',
  imports: [Icon, LoadError, PageHeader],
  templateUrl: './cycle-editor-page.html',
  styleUrl: './cycle-editor-page.scss',
})
export class CycleEditorPage {
  /** The cycle's id; absent for a new one. */
  readonly id = input<string>();
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  protected readonly kinds = KINDS;

  protected readonly campuses = load(() =>
    this.api.get<Page<Campus>>('institution/campuses', { page_size: 200, active: 1 }),
  );
  protected readonly data = load(
    (): Observable<AdmissionCycle | null> =>
      this.id() ? this.api.get<AdmissionCycle>(`institution/admissions/cycles/${this.id()}`) : of(null),
    () => this.id(),
  );

  protected readonly name = signal('');
  protected readonly entryYear = signal(new Date().getFullYear() + 1);
  protected readonly opensOn = signal(iso(new Date()));
  protected readonly closesOn = signal(iso(new Date(Date.now() + 60 * 86400000)));
  protected readonly instructions = signal('');
  protected readonly places = signal<PlaceRow[]>([]);
  protected readonly questions = signal<CycleQuestion[]>([]);
  protected readonly documents = signal<CycleDocument[]>([]);
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');

  protected readonly draft = computed(() => (this.data.value()?.status ?? 'draft') === 'draft');

  constructor() {
    effect(() => {
      const cycle = this.data.value();
      if (cycle) {
        this.name.set(cycle.name);
        this.entryYear.set(cycle.entry_year);
        this.opensOn.set(cycle.opens_on);
        this.closesOn.set(cycle.closes_on);
        this.instructions.set(cycle.instructions);
        this.places.set(
          cycle.places.map((p) => ({ code: p.code, label: p.label, campus: p.campus?.id ?? '', seats: p.seats, in_use: p.in_use })),
        );
        this.questions.set(cycle.questions.map((q) => ({ ...q, options: [...q.options] })));
        this.documents.set(cycle.documents.map((d) => ({ ...d })));
      }
    });
  }

  protected value(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  protected addPlace(): void {
    this.places.update((rows) => [...rows, { code: '', label: '', campus: '', seats: 30 }]);
  }

  protected addQuestion(): void {
    this.questions.update((rows) => [...rows, { code: '', label: '', help: '', kind: 'text', options: [], required: true }]);
  }

  protected addDocument(): void {
    this.documents.update((rows) => [...rows, { code: '', label: '', help: '', required: true }]);
  }

  protected remove<T>(list: { update: (fn: (rows: T[]) => T[]) => void }, index: number): void {
    list.update((rows) => rows.filter((_, i) => i !== index));
  }

  protected set<T extends object>(list: { update: (fn: (rows: T[]) => T[]) => void }, index: number, patch: Partial<T>): void {
    list.update((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  protected problem(field: string): string {
    return this.errors()[field] ?? '';
  }

  private body() {
    return {
      name: this.name(),
      entry_year: this.entryYear(),
      opens_on: this.opensOn(),
      closes_on: this.closesOn(),
      instructions: this.instructions(),
      places: this.places().map(({ code, label, campus, seats }) => ({ code, label, campus: campus || null, seats })),
      questions: this.questions(),
      documents: this.documents(),
    };
  }

  private failed(err: unknown): void {
    this.busy.set(false);
    const fields = fieldErrors(err);
    this.errors.set(fields);
    this.error.set(Object.keys(fields).length ? 'Check the highlighted fields.' : apiErrorMessage(err));
  }

  protected save(): void {
    const cycle = this.data.value();
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    const request = cycle
      ? this.api.patch<AdmissionCycle>(`institution/admissions/cycles/${cycle.id}`, { ...this.body(), version: cycle.version })
      : this.api.post<AdmissionCycle>('institution/admissions/cycles', this.body());
    request.subscribe({
      next: (saved) => {
        this.busy.set(false);
        this.toasts.show('Cycle saved.');
        if (cycle) {
          this.data.value.set(saved);
        } else {
          void this.router.navigate(['/app/admissions/cycles', saved.id], { replaceUrl: true });
        }
      },
      error: (err) => this.failed(err),
    });
  }

  protected async move(step: 'publish' | 'close'): Promise<void> {
    const cycle = this.data.value();
    if (!cycle) {
      return;
    }
    const yes = await this.confirm.ask(
      step === 'publish'
        ? {
            title: `Open ${cycle.name} for applications?`,
            message: 'Families can apply from your public page. The places, questions and documents can no longer be changed.',
            confirmLabel: 'Open for applications',
          }
        : {
            title: `Close ${cycle.name}?`,
            message: 'No new applications or submissions. Applications already in hand carry on.',
            confirmLabel: 'Close',
            tone: 'danger',
          },
    );
    if (!yes) {
      return;
    }
    this.busy.set(true);
    this.api.post<AdmissionCycle>(`institution/admissions/cycles/${cycle.id}/${step}`, { version: cycle.version }).subscribe({
      next: (saved) => {
        this.busy.set(false);
        this.data.value.set(saved);
        this.toasts.show(step === 'publish' ? 'Open for applications.' : 'Closed.');
      },
      error: (err) => this.failed(err),
    });
  }
}
