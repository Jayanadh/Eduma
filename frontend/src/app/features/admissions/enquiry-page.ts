import { Component, computed, inject, input, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { Enquiry } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { date, dateTime } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** One enquiry: who asked what, its follow-ups, and what happens next (assign, follow up, link, close). */
@Component({
  selector: 'app-enquiry-page',
  imports: [LoadError, PageHeader, ReactiveFormsModule, RouterLink],
  templateUrl: './enquiry-page.html',
  styles: `
    .timeline {
      display: flex;
      flex-direction: column;
      gap: 12px;
      margin: 0;
      padding: 0;
      list-style: none;

      li {
        display: flex;
        flex-direction: column;
      }
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
  `,
})
export class EnquiryPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  protected readonly auth = inject(AuthStore);
  protected readonly date = date;
  protected readonly dateTime = dateTime;
  protected readonly data = load(
    () => this.api.get<Enquiry>(`institution/admissions/enquiries/${this.id()}`),
    () => this.id(),
  );
  protected readonly assignees = load(() =>
    this.api.get<{ id: string; full_name: string }[]>('institution/admissions/enquiries/assignees'),
  );
  protected readonly open = computed(() => ['open', 'following_up'].includes(this.data.value()?.status ?? ''));
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly follow = inject(NonNullableFormBuilder).group({ how: ['phone'], note: [''], next_follow_up_on: [''] });

  private base(e: Enquiry): string {
    return `institution/admissions/enquiries/${e.id}`;
  }

  private settle(updated: Enquiry, message: string): void {
    this.busy.set(false);
    this.data.value.set(updated);
    this.toasts.show(message);
  }

  private failed(err: unknown): void {
    this.busy.set(false);
    const fields = fieldErrors(err);
    this.errors.set(fields);
    if (!Object.keys(fields).length) {
      this.toasts.show(apiErrorMessage(err), 'danger');
      this.data.reload();
    }
  }

  protected assign(e: Enquiry, userId: string | null): void {
    this.busy.set(true);
    this.errors.set({});
    this.api.patch<Enquiry>(this.base(e), { version: e.version, assigned_to: userId }).subscribe({
      next: (updated) => this.settle(updated, userId ? 'Assigned.' : 'Unassigned.'),
      error: (err) => this.failed(err),
    });
  }

  protected addFollowUp(e: Enquiry): void {
    const value = this.follow.getRawValue();
    this.busy.set(true);
    this.errors.set({});
    const body = { how: value.how, note: value.note, next_follow_up_on: value.next_follow_up_on || null };
    this.api.post<Enquiry>(`${this.base(e)}/follow-ups`, body).subscribe({
      next: (updated) => {
        this.follow.reset({ how: 'phone', note: '', next_follow_up_on: '' });
        this.settle(updated, 'Follow-up recorded.');
      },
      error: (err) => this.failed(err),
    });
  }

  protected async convert(e: Enquiry): Promise<void> {
    const number = await this.confirm.prompt({
      title: 'Link to an application',
      message: 'The family has applied. Enter their application number, such as A2027-0004.',
      label: 'Application number',
      required: true,
      confirmLabel: 'Link',
    });
    if (number !== null) {
      this.busy.set(true);
      this.api.post<Enquiry>(`${this.base(e)}/convert`, { version: e.version, application_number: number }).subscribe({
        next: (updated) => this.settle(updated, 'Linked to the application.'),
        error: (err) => this.failed(err),
      });
    }
  }

  protected async close(e: Enquiry): Promise<void> {
    const reason = await this.confirm.prompt({
      title: `Close ${e.number}?`,
      message: 'You can reopen it later.',
      label: 'Why?',
      type: 'textarea',
      required: true,
      confirmLabel: 'Close',
    });
    if (reason !== null) {
      this.busy.set(true);
      this.api.post<Enquiry>(`${this.base(e)}/close`, { version: e.version, reason }).subscribe({
        next: (updated) => this.settle(updated, 'Closed.'),
        error: (err) => this.failed(err),
      });
    }
  }

  protected reopen(e: Enquiry): void {
    this.busy.set(true);
    this.api.post<Enquiry>(`${this.base(e)}/reopen`, { version: e.version }).subscribe({
      next: (updated) => this.settle(updated, 'Reopened.'),
      error: (err) => this.failed(err),
    });
  }
}
