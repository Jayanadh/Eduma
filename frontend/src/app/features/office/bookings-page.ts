import { Component, inject, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { AssetT } from './assets-page';
import { OFFICE_STYLES } from './office-styles';

type BookingT = {
  id: string;
  asset: { id: string; tag: string; name: string };
  starts_at: string;
  ends_at: string;
  purpose: string;
  booked_by: string;
  canceled: boolean;
  mine: boolean;
};

/** Booking labs and equipment (S10B-09): two bookings never overlap, and nothing in maintenance can be booked. */
@Component({
  selector: 'app-bookings-page',
  imports: [PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Campus" title="Lab booking" subtitle="Book a lab or equipment for a time." />
      <section class="card stack section">
        <form id="book" class="row" (submit)="$event.preventDefault(); book($any($event.target))">
          <div class="field grow"><label for="book-asset">Lab or equipment</label>
            <select id="book-asset">@for (a of assets.value() ?? []; track a.id) { <option [value]="a.id">{{ a.name }} ({{ a.tag }})</option> }</select></div>
          <div class="field"><label for="book-from">From</label><input id="book-from" type="datetime-local" required /></div>
          <div class="field"><label for="book-to">To</label><input id="book-to" type="datetime-local" required /></div>
          <div class="field grow"><label for="book-purpose">For</label><input id="book-purpose" maxlength="150" required /></div>
          <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Book</button>
        </form>
      </section>
      <section class="card stack section">
        <h2 class="card-title">Coming up</h2>
        <ul class="rows">
          @for (b of bookings.value() ?? []; track b.id) {
            <li>
              <span><strong>{{ b.asset.name }}</strong> <span class="muted small">· {{ dateTime(b.starts_at) }} → {{ dateTime(b.ends_at) }} · {{ b.purpose }} · {{ b.booked_by }}</span></span>
              @if (b.mine) {
                <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Cancel booking of ' + b.asset.name" (click)="cancel(b)">Cancel</button>
              }
            </li>
          } @empty {
            <li class="muted small">Nothing booked.</li>
          }
        </ul>
      </section>
    </div>
  `,
  styles: [OFFICE_STYLES],
})
export class BookingsPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly dateTime = dateTime;
  protected readonly assets = load(() => this.api.get<AssetT[]>('institution/stores/assets'));
  protected readonly bookings = load(() => this.api.get<BookingT[]>('institution/stores/bookings'));
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        this.bookings.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected book(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value;
    const body = {
      asset: field('book-asset'),
      starts_at: new Date(field('book-from')).toISOString(),
      ends_at: new Date(field('book-to')).toISOString(),
      purpose: field('book-purpose').trim(),
    };
    this.run(this.api.post('institution/stores/bookings', body), 'Booked.', () => form.reset());
  }

  protected cancel(b: BookingT): void {
    this.run(this.api.post(`institution/stores/bookings/${b.id}/cancel`, {}), 'Booking canceled.');
  }
}
