import { Component, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { ApplicationDocument, StaffApplication } from '../../core/api/types';
import { date, dateTime } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/**
 * One application for reviewing staff: what the family sent, the documents to check, earlier submissions, internal
 * notes, and the next steps this stage and the viewer's roles allow.
 */
@Component({
  selector: 'app-application-review-page',
  imports: [LoadError, PageHeader, RouterLink],
  templateUrl: './application-review-page.html',
})
export class ApplicationReviewPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly dateTime = dateTime;
  protected readonly busy = signal(false);
  protected readonly note = signal('');

  protected readonly data = load(
    () => this.api.get<StaffApplication>(`institution/admissions/applications/${this.id()}`),
    () => this.id(),
  );

  protected base(a: StaffApplication): string {
    return `institution/admissions/applications/${a.id}`;
  }

  protected download(a: StaffApplication, doc: ApplicationDocument): string {
    return `/api/v1/${this.base(a)}/documents/${doc.id}`;
  }

  protected answerText(value: unknown): string {
    return value === true ? 'Yes' : value === false ? 'No' : value ? String(value) : '—';
  }

  private send(path: string, body: object, message: string): void {
    this.busy.set(true);
    this.api.post<StaffApplication>(path, body).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.data.value.set(updated);
        this.toasts.show(message);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
        this.data.reload();
      },
    });
  }

  protected step(a: StaffApplication, step: string, message: string): void {
    this.send(`${this.base(a)}/${step}`, { version: a.version }, message);
  }

  protected async requestInformation(a: StaffApplication): Promise<void> {
    const message = await this.confirm.prompt({
      title: 'Ask the family for more',
      message: 'The application reopens for them with your message. Be specific.',
      label: 'What do they need to give or change?',
      type: 'textarea',
      required: true,
      confirmLabel: 'Send',
    });
    if (message !== null) {
      this.send(`${this.base(a)}/request-information`, { version: a.version, message }, 'Sent to the family.');
    }
  }

  protected async reject(a: StaffApplication): Promise<void> {
    const reason = await this.confirm.prompt({
      title: `Not offer ${a.learner_name} a place?`,
      message: 'The family sees your reason.',
      label: 'Reason',
      type: 'textarea',
      required: true,
      confirmLabel: 'Not offered a place',
      tone: 'danger',
    });
    if (reason !== null) {
      this.send(`${this.base(a)}/reject`, { version: a.version, reason }, 'Recorded.');
    }
  }

  protected async offer(a: StaffApplication): Promise<void> {
    const expires = await this.confirm.prompt({
      title: `Offer ${a.place.label} to ${a.learner_name}?`,
      message: 'The family must accept by the date you choose; until then the place is held for them.',
      label: 'Accept by',
      type: 'date',
      required: true,
      confirmLabel: 'Offer the place',
    });
    if (expires !== null) {
      this.send(`${this.base(a)}/offer`, { version: a.version, expires_on: expires }, 'Place offered.');
    }
  }

  protected async enroll(a: StaffApplication): Promise<void> {
    const password = await this.confirm.firstPassword(
      `First password for ${a.learner_name}`,
      "Enrolling makes the student record and the student's own login. Hand this password over; they change it at first sign-in.",
      'Enroll',
    );
    if (password !== null) {
      this.send(`${this.base(a)}/enroll`, { version: a.version, password }, `${a.learner_name} is enrolled.`);
    }
  }

  protected async reviewDocument(a: StaffApplication, doc: ApplicationDocument, ok: boolean): Promise<void> {
    let note = '';
    if (!ok) {
      const asked = await this.confirm.prompt({
        title: `${doc.label} needs replacing`,
        message: 'The family sees this note.',
        label: 'What is wrong',
        type: 'text',
        required: true,
        confirmLabel: 'Ask for a new one',
      });
      if (asked === null) {
        return;
      }
      note = asked;
    }
    const path = `${this.base(a)}/documents/${doc.id}/${ok ? 'verify' : 'reject'}`;
    this.send(path, { version: doc.version, note }, ok ? 'Document checked.' : 'Family asked for a new one.');
  }

  protected addNote(a: StaffApplication): void {
    if (!this.note().trim()) {
      return;
    }
    this.api.post<StaffApplication>(`${this.base(a)}/notes`, { text: this.note() }).subscribe({
      next: (updated) => {
        this.note.set('');
        this.data.value.set(updated);
      },
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }
}
