import { Component, computed, inject, input, output, signal } from '@angular/core';
import { of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { CurriculumSummary, Program, StudentRecord } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { load } from '../../core/load';
import { ToastService } from '../../ui/toast';

/** The program and regulation a college student follows, and changing it to another published regulation. */
@Component({
  selector: 'app-program-section',
  template: `
    @if (shown()) {
      <section class="card stack">
        <h2 class="card-title">Program and regulation</h2>
        @if (student().enrollment?.program; as program) {
          <p class="small"><strong>{{ program.name }}</strong> ({{ program.code }})</p>
          <p class="muted small">{{ student().enrollment?.curriculum?.label ?? 'No regulation pinned yet' }}</p>
        } @else {
          <p class="muted small">Not in a program.</p>
        }
        @if (editing()) {
          <form class="stack" (submit)="$event.preventDefault(); save()">
            <div class="field">
              <label for="pin-program">Program</label>
              <select id="pin-program" (change)="pick($any($event.target).value)">
                <option value="">None</option>
                @for (p of programs.value() ?? []; track p.id) {
                  @if (p.is_active || p.id === student().enrollment?.program?.id) {
                    <option [value]="p.id" [selected]="p.id === program()">{{ p.name }}</option>
                  }
                }
              </select>
            </div>
            <div class="field">
              <label for="pin-curriculum">Regulation</label>
              <select id="pin-curriculum" (change)="curriculum.set($any($event.target).value)">
                <option value="">Program only</option>
                @for (c of published(); track c.id) {
                  <option [value]="c.id" [selected]="c.id === curriculum()">{{ c.regulation }} rev {{ c.revision }}</option>
                }
              </select>
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Save</button>
              <button type="button" class="btn btn-secondary btn-sm" (click)="editing.set(false)">Cancel</button>
            </div>
          </form>
        } @else if (student().can_change_program && higher()) {
          <div><button type="button" class="btn btn-secondary btn-sm" (click)="start()">Change</button></div>
        }
      </section>
    }
  `,
})
export class ProgramSection {
  readonly student = input.required<StudentRecord>();
  readonly changed = output<StudentRecord>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly higher = inject(AuthStore).higher;
  protected readonly shown = computed(() => this.higher() || !!this.student().enrollment?.program);
  protected readonly editing = signal(false);
  protected readonly program = signal('');
  protected readonly curriculum = signal('');
  protected readonly busy = signal(false);
  protected readonly programs = load(
    () => (this.editing() ? this.api.get<Program[]>('institution/academics/programs') : of([] as Program[])),
    () => this.editing(),
  );
  protected readonly curricula = load(
    () =>
      this.editing() && this.program()
        ? this.api.get<CurriculumSummary[]>(`institution/academics/programs/${this.program()}/curricula`)
        : of([] as CurriculumSummary[]),
    () => [this.editing(), this.program()],
  );
  /** Only a published regulation can be chosen; the one already pinned stays listed if it has since retired. */
  protected readonly published = computed(() =>
    (this.curricula.value() ?? []).filter(
      (c) => c.status === 'published' || c.id === this.student().enrollment?.curriculum?.id,
    ),
  );

  protected start(): void {
    this.program.set(this.student().enrollment?.program?.id ?? '');
    this.curriculum.set(this.student().enrollment?.curriculum?.id ?? '');
    this.editing.set(true);
  }

  protected pick(program: string): void {
    this.program.set(program);
    this.curriculum.set('');
  }

  protected save(): void {
    const student = this.student();
    const body = { version: student.version, program: this.program() || null, curriculum: this.curriculum() || null };
    this.busy.set(true);
    this.api.post<StudentRecord>(`institution/students/${student.id}/program`, body).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.editing.set(false);
        this.changed.emit(updated);
        this.toasts.show('Program and regulation saved.');
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
