import { Component, computed, inject, input, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { MoveUpRow, Page, RosterRow, ClassSection, StudentListItem, Subject } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { SearchBox } from '../../ui/search-box';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { ToastService } from '../../ui/toast';

const ACTIONS: Record<MoveUpRow['action'], string> = {
  move: 'Moves up',
  already_placed: 'Already placed next year',
  withdrawn: 'Withdrawn',
  not_enrolled: 'Not enrolled',
};

/** One section: its teachers, who is in it, placing students, and moving it on to next year. */
@Component({
  selector: 'app-section-page',
  imports: [LoadError, PageHeader, SearchBox],
  templateUrl: './section-page.html',
  styleUrl: './section-page.scss',
})
export class SectionPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly confirm = inject(ConfirmDialog);
  protected readonly actions = ACTIONS;
  private base(): string {
    return `institution/academics/sections/${this.id()}`;
  }
  protected readonly data = load(
    () => this.api.get<ClassSection>(this.base()),
    () => this.id(),
  );
  protected readonly roster = load(
    () => this.api.get<RosterRow[]>(`${this.base()}/students`),
    () => this.id(),
  );
  protected readonly staff = load(() => this.api.get<{ id: string; full_name: string }[]>('institution/academics/staff'));
  protected readonly subjects = load(() => this.api.get<Subject[]>('institution/academics/subjects'));
  protected readonly all = load(() => this.api.get<Page<ClassSection>>('institution/academics/sections', { page_size: 200 }));
  protected readonly sameYear = computed(() =>
    (this.all.value()?.results ?? []).filter((s) => s.year.id === this.data.value()?.year.id && s.id !== this.id()),
  );
  protected readonly laterYears = computed(() =>
    (this.all.value()?.results ?? []).filter((s) => s.year.id !== this.data.value()?.year.id),
  );
  protected readonly busy = signal(false);
  protected readonly search = signal('');
  protected readonly found = load(
    () =>
      this.search().length >= 3
        ? this.api.get<Page<StudentListItem>>('institution/students', { search: this.search(), status: 'active' })
        : of({ count: 0, next: null, previous: null, results: [] as StudentListItem[] }),
    () => this.search(),
  );
  protected readonly chosen = signal<{ id: string; label: string }[]>([]);
  protected readonly teacher = signal('');
  protected readonly subject = signal('');
  protected readonly target = signal('');
  protected readonly mode = signal<'promote' | 'repeat'>('promote');
  protected readonly preview = signal<MoveUpRow[] | null>(null);
  /** Students the registrar unticked: they stay behind (e.g. held back) while the rest move up. */
  protected readonly staying = signal<ReadonlySet<string>>(new Set());
  protected readonly moving = computed(() =>
    (this.preview() ?? []).filter((row) => row.action === 'move' && !this.staying().has(row.student.id)),
  );

  protected toggle(id: string, moves: boolean): void {
    this.staying.update((ids) => {
      const next = new Set(ids);
      if (moves) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  protected choose(id: string, label: string): void {
    this.chosen.update((rows) => (rows.some((r) => r.id === id) ? rows : [...rows, { id, label }]));
  }

  protected unchoose(id: string): void {
    this.chosen.update((rows) => rows.filter((r) => r.id !== id));
  }

  private run<T>(request: Observable<T>, message: string, after: (result: T) => void = () => undefined): void {
    this.busy.set(true);
    request.subscribe({
      next: (result) => {
        this.busy.set(false);
        this.toasts.show(message);
        after(result);
        this.data.reload();
        this.roster.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected place(): void {
    const ids = this.chosen().map((r) => r.id);
    this.run(this.api.post(`${this.base()}/students`, { students: ids }), `${ids.length} placed.`, () => this.chosen.set([]));
  }

  protected async remove(row: RosterRow): Promise<void> {
    const yes = await this.confirm.ask({
      title: `Take ${row.student.full_name} out of this class?`,
      message: 'They can be placed in another class this year.',
      confirmLabel: 'Take out',
    });
    if (yes) {
      this.run(this.api.delete(`${this.base()}/students/${row.student.id}`), `${row.student.full_name} taken out.`);
    }
  }

  protected moveTo(row: RosterRow, section: string): void {
    if (section) {
      this.run(this.api.post(`${this.base()}/students/${row.student.id}/move`, { section }), `${row.student.full_name} moved.`);
    }
  }

  protected addTeacher(): void {
    const body = { membership: this.teacher(), subject: this.subject() || null };
    this.run(this.api.post(`${this.base()}/teachers`, body), 'Teacher added.');
  }

  protected endTeacher(assignment: string): void {
    this.run(this.api.post(`${this.base()}/teachers/${assignment}/end`, {}), 'Teacher removed from this section.');
  }

  protected showPreview(): void {
    this.busy.set(true);
    this.api.post<MoveUpRow[]>(`${this.base()}/move-up/preview`, { target: this.target(), mode: this.mode() }).subscribe({
      next: (rows) => {
        this.busy.set(false);
        this.staying.set(new Set());
        this.preview.set(rows);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected moveUp(): void {
    const body = { target: this.target(), mode: this.mode(), students: this.moving().map((row) => row.student.id) };
    this.run(this.api.post<{ moved: number }>(`${this.base()}/move-up`, body), 'Moved up.', () => this.preview.set(null));
  }
}
