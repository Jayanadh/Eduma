import { Component, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { catchError, of } from 'rxjs';
import { AssessmentT, AttendanceSessionT, ClassAssignment, ClassSessionT } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ToastService } from '../../ui/toast';

/** On a class a teacher teaches: take a register for a day, and post or open assignments. */
@Component({
  selector: 'app-class-tools',
  imports: [RouterLink],
  template: `
    <section class="card stack section">
      <h2 class="card-title">Attendance</h2>
      <form id="take-attendance" class="row" (submit)="$event.preventDefault(); take($any($event.target))">
        <div class="field"><label for="attendance-date">Day</label><input id="attendance-date" type="date" [value]="today" /></div>
        <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Take attendance</button>
      </form>
    </section>
    @if (assessments().length) {
      <section class="card stack section">
        <h2 class="card-title">Assessments</h2>
        <ul class="bullets">
          @for (a of assessments(); track a.id) {
            <li><a [routerLink]="['/app/results/assessments', a.id]">{{ a.title }}</a> <span class="muted small meta">{{ a.state_label }}</span></li>
          }
        </ul>
      </section>
    }
    @if (comms()) {
      <section class="card stack section">
        <h2 class="card-title">Online classes</h2>
        <ul class="bullets">
          @for (s of online(); track s.id) { <li><a [routerLink]="['/app/classes', s.id]">{{ s.title }}</a> <span class="muted small meta">{{ date(s.starts_at) }} · {{ s.state_label }}</span></li> }
        </ul>
        <form id="schedule-class" class="row" (submit)="$event.preventDefault(); schedule($any($event.target))">
          <div class="field"><label for="class-title">Title</label><input id="class-title" /></div>
          <div class="field"><label for="class-starts">Starts</label><input id="class-starts" type="datetime-local" /></div>
          <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Schedule online class</button>
        </form>
      </section>
    }
    <section class="card stack section">
      <h2 class="card-title">Assignments</h2>
      <ul class="bullets">
        @for (a of mine(); track a.id) {
          <li><a [routerLink]="['/app/teaching/assignments', a.id]">{{ a.title }}</a> <span class="muted small meta">due {{ date(a.due_at) }}</span></li>
        } @empty {
          <li class="muted small">None yet.</li>
        }
      </ul>
      <form id="post-assignment" class="stack" (submit)="$event.preventDefault(); post($any($event.target))">
        <div class="field"><label for="assignment-title">Title</label><input id="assignment-title" /></div>
        <div class="field"><label for="assignment-instructions">Instructions</label><textarea id="assignment-instructions" rows="3"></textarea></div>
        <div class="field"><label for="assignment-due">Due</label><input id="assignment-due" type="datetime-local" /></div>
        <div><button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Post assignment</button></div>
      </form>
    </section>
  `,
  styles: `
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: end;
    }

    .bullets {
      margin: 0;
      padding-left: 18px;
    }
  `,
})
export class ClassTools {
  readonly kind = input.required<'section' | 'offering'>();
  readonly target = input.required<string>();
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly today = new Date().toLocaleDateString('en-CA');
  private readonly assignments = load(() => this.api.get<ClassAssignment[]>('teaching/assignments'));
  protected mine(): ClassAssignment[] {
    return (this.assignments.value() ?? []).filter((a) => a.target.id === this.target());
  }
  // Marks are entered on the assessment page; shown when Assessment and results is on (404 otherwise, so empty).
  private readonly marking = load(() =>
    this.api.get<AssessmentT[]>('institution/results/assessments', { [this.kind()]: this.target() }).pipe(catchError(() => of([]))),
  );
  protected assessments(): AssessmentT[] {
    return this.marking.value() ?? [];
  }
  private readonly auth = inject(AuthStore);
  protected comms(): boolean {
    return this.auth.user()?.membership?.modules_enabled?.includes('communication') ?? false;
  }
  private readonly sessions = load(() =>
    this.comms() ? this.api.get<ClassSessionT[]>('communication/classes').pipe(catchError(() => of([]))) : of([] as ClassSessionT[]),
  );
  protected online(): ClassSessionT[] {
    return (this.sessions.value() ?? []).filter((s) => s.target.id === this.target());
  }
  protected readonly busy = signal(false);

  protected schedule(form: HTMLFormElement): void {
    const title = form.querySelector<HTMLInputElement>('#class-title')!.value.trim();
    const starts = form.querySelector<HTMLInputElement>('#class-starts')!.value;
    this.busy.set(true);
    this.api
      .post<ClassSessionT>('communication/classes', { [this.kind()]: this.target(), title, starts_at: starts ? new Date(starts).toISOString() : '' })
      .subscribe({
        next: (made) => {
          this.busy.set(false);
          this.router.navigate(['/app/classes', made.id]);
        },
        error: (err) => {
          this.busy.set(false);
          this.toasts.show(apiErrorMessage(err), 'danger');
        },
      });
  }

  protected take(form: HTMLFormElement): void {
    const day = form.querySelector<HTMLInputElement>('#attendance-date')!.value;
    this.busy.set(true);
    this.api.post<AttendanceSessionT>('teaching/attendance', { [this.kind()]: this.target(), date: day }).subscribe({
      next: (session) => {
        this.busy.set(false);
        this.router.navigate(['/app/teaching/attendance', session.id]);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected post(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLTextAreaElement>(`#${id}`)!.value.trim();
    const due = field('assignment-due');
    const body = {
      [this.kind()]: this.target(),
      title: field('assignment-title'),
      instructions: field('assignment-instructions'),
      due_at: due ? new Date(due).toISOString() : '',
    };
    this.busy.set(true);
    this.api.post<ClassAssignment>('teaching/assignments', body).subscribe({
      next: () => {
        this.busy.set(false);
        form.reset();
        this.toasts.show('Assignment posted.');
        this.assignments.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
