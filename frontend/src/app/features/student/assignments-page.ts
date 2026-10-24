import { Component, inject, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { ClassAssignment } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from '../apply/portal-frame';

/** A student's assignments: hand in a written answer; it can be changed until the teacher gives feedback. */
@Component({
  selector: 'app-student-assignments-page',
  imports: [LoadError, PortalFrame],
  template: `
    <app-portal-frame heading="Assignments">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @for (a of data.value() ?? []; track a.id) {
        <section class="card stack">
          <h2 class="card-title">{{ a.title }}</h2>
          <p class="muted small">{{ a.target.label }} · due {{ dateTime(a.due_at) }}</p>
          <p class="instructions">{{ a.instructions }}</p>
          @if (a.submission?.feedback) {
            <p class="small"><strong>Your answer:</strong> {{ a.submission?.text }}</p>
            <p class="small"><strong>Feedback:</strong> {{ a.submission?.feedback }}</p>
          } @else {
            <form class="stack" [id]="'answer-' + a.id" (submit)="$event.preventDefault(); handIn(a, $any($event.target))">
              <label [for]="'answer-text-' + a.id" class="small">{{ a.submission ? 'Handed in ' + dateTime(a.submission.submitted_at) + (a.submission.late ? ' (late)' : '') + ' — you can still change it' : 'Your answer' }}</label>
              <textarea [id]="'answer-text-' + a.id" rows="4" [value]="a.submission?.text ?? ''"></textarea>
              <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">{{ a.submission ? 'Update' : 'Hand in' }}</button></div>
            </form>
          }
        </section>
      } @empty {
        <p class="muted">No assignments right now.</p>
      }
    </app-portal-frame>
  `,
  styles: `
    .instructions {
      white-space: pre-wrap;
    }
  `,
})
export class StudentAssignmentsPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly dateTime = dateTime;
  protected readonly data = load(() => this.api.get<ClassAssignment[]>('student/assignments'));
  protected readonly busy = signal(false);

  protected handIn(a: ClassAssignment, form: HTMLFormElement): void {
    const text = form.querySelector<HTMLTextAreaElement>(`#answer-text-${a.id}`)!.value.trim();
    if (!text) {
      return;
    }
    this.busy.set(true);
    this.api.post(`student/assignments/${a.id}/submit`, { text }).subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show('Handed in.');
        this.data.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
