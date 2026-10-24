import { Component, inject, input, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { Offering, OfferingTeacher } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** One offering: its status and who teaches it. Its class list arrives with course registration. */
@Component({
  selector: 'app-offering-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as o) {
        <app-page-header
          eyebrow="Offering"
          [title]="o.label + ' · ' + o.course.title"
          [subtitle]="o.term.year + ' ' + o.term.name + ' · ' + o.campus.name + ' · ' + o.capacity + ' seats · ' + o.status_label"
          backLink="/app/academics/offerings"
        >
          @if (o.can_manage && o.term.year_status !== 'closed') {
            @if (o.status === 'planned') {
              <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="setStatus(o, 'open')">Open for registration</button>
            }
            @if (o.status === 'open') {
              <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="setStatus(o, 'closed')">Close</button>
            }
            @if (o.status === 'planned' || o.status === 'open') {
              <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="setStatus(o, 'cancelled')">Cancel offering</button>
            }
          }
        </app-page-header>
        <p class="muted small section">
          {{ o.course.credits }} credits{{ o.linked_to ? ' · goes with ' + o.linked_to.label : '' }}{{ o.linked.length ? ' · ' + o.linked.join(', ') + ' go with it' : '' }}
        </p>
        <section class="card stack section">
          <h2 class="card-title">Teachers</h2>
          <ul class="rows">
            @for (t of o.teachers; track t.id) {
              <li>
                <span>{{ t.membership.full_name }} <span class="muted small">· from {{ date(t.starts_on) }}{{ t.ends_on ? ' to ' + date(t.ends_on) : '' }}</span></span>
                @if (o.can_manage && t.in_effect) {
                  <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'End ' + t.membership.full_name" [disabled]="busy()" (click)="end(t)">End</button>
                }
              </li>
            } @empty {
              <li class="muted small">Nobody assigned yet.</li>
            }
          </ul>
          @if (o.can_manage && (o.status === 'planned' || o.status === 'open') && o.term.year_status !== 'closed') {
            <form id="add-teacher" class="row" (submit)="$event.preventDefault(); assign($any($event.target))">
              <div class="field">
                <label for="new-teacher">Teacher</label>
                <select id="new-teacher">
                  @for (s of staff.value() ?? []; track s.id) { <option [value]="s.id">{{ s.full_name }}</option> }
                </select>
              </div>
              <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Assign</button>
            </form>
          }
        </section>
      }
    </div>
  `,
  styles: `
    .rows {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;

      li {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
    }

    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: end;
    }
  `,
})
export class OfferingPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly confirm = inject(ConfirmDialog);
  protected readonly date = date;
  private base(): string {
    return `institution/academics/offerings/${this.id()}`;
  }
  protected readonly data = load(
    () => this.api.get<Offering>(this.base()),
    () => this.id(),
  );
  protected readonly staff = load(() => this.api.get<{ id: string; full_name: string }[]>('institution/academics/staff'));
  protected readonly busy = signal(false);

  private run(request: Observable<Offering>, message: string): void {
    this.busy.set(true);
    request.subscribe({
      next: (result) => {
        this.busy.set(false);
        this.data.value.set(result);
        this.toasts.show(message);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
        this.data.reload();
      },
    });
  }

  protected async setStatus(o: Offering, status: 'open' | 'closed' | 'cancelled'): Promise<void> {
    if (status !== 'open') {
      const yes = await this.confirm.ask({
        title: status === 'closed' ? `Close ${o.label}?` : `Cancel ${o.label}?`,
        message: 'This can’t be undone. Its teachers stay on record.',
        confirmLabel: status === 'closed' ? 'Close' : 'Cancel offering',
      });
      if (!yes) {
        return;
      }
    }
    this.run(this.api.patch<Offering>(this.base(), { version: o.version, status }), `${o.label} is now ${status}.`);
  }

  protected assign(form: HTMLFormElement): void {
    const membership = form.querySelector<HTMLSelectElement>('#new-teacher')?.value;
    if (membership) {
      this.run(this.api.post<Offering>(`${this.base()}/teachers`, { membership }), 'Teacher assigned.');
    }
  }

  protected async end(t: OfferingTeacher): Promise<void> {
    const yes = await this.confirm.ask({
      title: `End ${t.membership.full_name}'s teaching here?`,
      message: 'Their assignment ends today and stays on record.',
      confirmLabel: 'End',
    });
    if (yes) {
      this.run(this.api.post<Offering>(`${this.base()}/teachers/${t.id}/end`, {}), 'Assignment ended.');
    }
  }
}
