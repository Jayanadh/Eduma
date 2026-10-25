import { Component, inject, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

type RouteT = { id: string; name: string; vehicle: string; capacity: number; stops: { name: string; time: string }[] };
type TripT = {
  id: string;
  route: string;
  date: string;
  direction: string;
  state: string;
  riders: { student: string; name: string; stop: string }[];
  boardings: { student: string; boarded_at: string; dropped_at: string | null; handed_to: string }[];
};

/** Transport (S10A-05..07): vehicles, routes and riders for the office; today's trips with boarding and safe
 * drop-off for the crew. */
@Component({
  selector: 'app-transport-page',
  imports: [PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Campus" title="Transport" subtitle="A route never carries more riders than its vehicle seats; drop-off only to an approved pickup." />
      @for (t of trips.value() ?? []; track t.id) {
        <section class="card stack section">
          <h2 class="card-title">{{ t.route }} · {{ t.direction === 'home' ? 'home' : 'to school' }} · {{ t.state }}</h2>
          <div class="actions">
            @for (s of next(t.state); track s) { <button type="button" class="btn btn-secondary btn-sm" (click)="move(t, s)">{{ s }}</button> }
          </div>
          <ul class="rows">
            @for (r of t.riders; track r.student) {
              <li>
                <span>{{ r.name }} <span class="muted small meta">{{ r.stop }}{{ status(t, r.student) }}</span></span>
                <span class="actions">
                  @if (!boarded(t, r.student)) { <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Board ' + r.name" (click)="board(t, r.student)">On board</button> }
                  @else if (!dropped(t, r.student)) {
                    <label class="sr-only" [for]="'handed-' + t.id + r.student">Handed to</label>
                    <input [id]="'handed-' + t.id + r.student" placeholder="Handed to" />
                    <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Drop ' + r.name" (click)="drop(t, r.student)">Dropped</button>
                  }
                </span>
              </li>
            }
          </ul>
        </section>
      } @empty {
        <p class="muted section">No trips today for you.</p>
      }
      <section class="card stack section">
        <h2 class="card-title">Routes</h2>
        <ul class="rows">@for (r of routes.value() ?? []; track r.id) { <li><span>{{ r.name }} <span class="muted small meta">{{ r.vehicle }} ({{ r.capacity }} seats) · @for (s of r.stops; track $index) { {{ s.name }} {{ s.time }} }</span></span></li> }</ul>
        <form id="add-vehicle" class="row" (submit)="$event.preventDefault(); vehicle($any($event.target))">
          <div class="field"><label for="v-reg">Vehicle</label><input id="v-reg" /></div>
          <div class="field"><label for="v-cap">Seats</label><input id="v-cap" type="number" min="1" /></div>
          <button type="submit" class="btn btn-secondary btn-sm">Add vehicle</button>
        </form>
        <form id="add-rider" class="row" (submit)="$event.preventDefault(); rider($any($event.target))">
          <div class="field"><label for="r-route">Route</label><select id="r-route">@for (r of routes.value() ?? []; track r.id) { <option [value]="r.id">{{ r.name }}</option> }</select></div>
          <div class="field"><label for="r-student">Student number</label><input id="r-student" /></div>
          <div class="field"><label for="r-stop">Stop</label><input id="r-stop" /></div>
          <div class="field"><label for="r-from">From</label><input id="r-from" type="date" /></div>
          <div class="field"><label for="r-to">To</label><input id="r-to" type="date" /></div>
          <button type="submit" class="btn btn-secondary btn-sm">Add rider</button>
        </form>
      </section>
    </div>
  `,
  styles: `
    .row,
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: end;
    }

  `,
})
export class TransportPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly trips = load(() => this.api.get<TripT[]>('institution/campus/trips', { date: new Date().toLocaleDateString('en-CA') }));
  protected readonly routes = load(() => this.api.get<RouteT[]>('institution/campus/routes'));
  protected readonly busy = signal(false);

  protected next(state: string): string[] {
    return ({ planned: ['dispatched', 'canceled'], dispatched: ['in_progress', 'canceled'], in_progress: ['completed'] } as Record<string, string[]>)[state] ?? [];
  }

  protected boarded(t: TripT, student: string): boolean {
    return t.boardings.some((b) => b.student === student);
  }

  protected dropped(t: TripT, student: string): boolean {
    return t.boardings.some((b) => b.student === student && b.dropped_at);
  }

  protected status(t: TripT, student: string): string {
    const b = t.boardings.find((x) => x.student === student);
    return b ? (b.dropped_at ? ` · handed to ${b.handed_to}` : ' · on board') : '';
  }

  private run(request: Observable<unknown>, done: string): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        this.trips.reload();
        this.routes.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected move(t: TripT, state: string): void {
    this.run(this.api.post(`institution/campus/trips/${t.id}/state`, { state }), `Trip ${state}.`);
  }

  protected board(t: TripT, student: string): void {
    this.run(this.api.post(`institution/campus/trips/${t.id}/board`, { student }), 'On board.');
  }

  protected drop(t: TripT, student: string): void {
    const handed = (document.getElementById(`handed-${t.id}${student}`) as HTMLInputElement | null)?.value.trim() ?? '';
    this.run(this.api.post(`institution/campus/trips/${t.id}/drop`, { student, handed_to: handed }), 'Dropped off.');
  }

  protected vehicle(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!.value.trim();
    this.run(this.api.post('institution/campus/vehicles', { registration: field('v-reg'), capacity: Number(field('v-cap')) }), 'Vehicle added.');
  }

  protected rider(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
    this.api.get<{ results: { id: string; number: string }[] }>('institution/students', { search: field('r-student') }).subscribe({
      next: (found) => {
        const student = found.results.find((s) => s.number === field('r-student'));
        if (!student) {
          this.toasts.show('No such student.', 'danger');
          return;
        }
        this.run(
          this.api.post('institution/campus/riders', {
            route: field('r-route'), student: student.id, stop: field('r-stop'), starts_on: field('r-from'), ends_on: field('r-to'),
          }),
          'Rider added.',
        );
      },
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }
}
