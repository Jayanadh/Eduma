import { Component, inject, input, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { ClassAssignment } from '../../core/api/types';
import { date, dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** One assignment's submissions, with feedback; feedback ends resubmitting. */
@Component({
  selector: 'app-assignment-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as a) {
        <app-page-header eyebrow="Assignment" [title]="a.title" [subtitle]="a.target.label + ' · due ' + dateTime(a.due_at)" backLink="/app/teaching" />
        <p class="section">{{ a.instructions }}</p>
        <div class="stack section">
          @for (s of a.submissions ?? []; track s.id) {
            <section class="card stack">
              <h2 class="card-title">{{ s.student.number }} · {{ s.student.full_name }}</h2>
              <p class="muted small">Handed in {{ dateTime(s.submitted_at) }}{{ s.late ? ' · late' : '' }}</p>
              <p class="answer">{{ s.text }}</p>
              @if (s.feedback) {
                <p class="small"><strong>Feedback:</strong> {{ s.feedback }}</p>
              } @else {
                <form class="row" [id]="'feedback-' + s.id" (submit)="$event.preventDefault(); feedback(s.id, $any($event.target))">
                  <label class="sr-only" [for]="'feedback-text-' + s.id">Feedback</label>
                  <input [id]="'feedback-text-' + s.id" placeholder="Feedback" />
                  <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Send</button>
                </form>
              }
            </section>
          } @empty {
            <p class="muted">Nothing handed in yet.</p>
          }
        </div>
      }
    </div>
  `,
  styles: `
    .answer {
      white-space: pre-wrap;
    }

    .row {
      display: flex;
      gap: 8px;

      input {
        flex: 1;
      }
    }
  `,
})
export class AssignmentPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly dateTime = dateTime;
  protected readonly data = load(
    () => this.api.get<ClassAssignment>(`teaching/assignments/${this.id()}`),
    () => this.id(),
  );
  protected readonly busy = signal(false);

  protected feedback(id: string, form: HTMLFormElement): void {
    const text = form.querySelector<HTMLInputElement>(`#feedback-text-${id}`)!.value.trim();
    if (!text) {
      return;
    }
    this.busy.set(true);
    this.api.post(`teaching/submissions/${id}/feedback`, { feedback: text }).subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show('Feedback sent.');
        this.data.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
