import { Component, inject, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { OwnCampus } from '../../core/api/types';
import { date, dateTime, money } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from '../apply/portal-frame';

/** A student's library loans, bus, and hostel place with out-passes — each shown while its module is on. */
@Component({
  selector: 'app-student-campus-page',
  imports: [LoadError, PortalFrame],
  template: `
    <app-portal-frame heading="Campus">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as c) {
        <section class="card stack">
          <h2 class="card-title">Library</h2>
          <ul class="bullets">
            @for (l of c.loans; track l.id) { <li>{{ l.title }} <span class="muted small meta">due {{ date(l.due_on) }} · {{ l.status }}@for (f of l.fines; track f.id) { · fine {{ money(f.amount) }}{{ f.waived_reason ? ' (waived)' : '' }} }</span></li> }
            @empty { <li class="muted small">No books out.</li> }
          </ul>
        </section>
        @if (c.transport; as t) {
          <section class="card stack"><h2 class="card-title">Bus</h2>
            <p class="small">{{ t.route }} · {{ t.stop }}{{ t.time ? ' at ' + t.time : '' }}@for (x of t.today; track $index) { · {{ x.direction === 'home' ? 'home' : 'to school' }}: {{ x.state }} }</p></section>
        }
        @if (c.hostel; as h) {
          <section class="card stack">
            <h2 class="card-title">Hostel</h2>
            <p class="small">Bed {{ h.bed ?? 'not assigned yet' }} · {{ h.state }}</p>
            <ul class="bullets">@for (o of c.out_passes; track o.id) { <li class="small">{{ dateTime(o.leaves_at) }} → {{ dateTime(o.returns_at) }} · {{ o.reason }} · {{ o.state }}</li> }</ul>
            <form id="out-pass" class="stack" (submit)="$event.preventDefault(); ask($any($event.target))">
              <div class="field"><label for="out-leaves">Leaving</label><input id="out-leaves" type="datetime-local" /></div>
              <div class="field"><label for="out-returns">Back by</label><input id="out-returns" type="datetime-local" /></div>
              <div class="field"><label for="out-reason">Reason</label><input id="out-reason" /></div>
              <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Ask for an out-pass</button></div>
            </form>
          </section>
        }
      }
    </app-portal-frame>
  `,
  styles: `
    .bullets {
      margin: 0;
      padding-left: 18px;
    }
  `,
})
export class StudentCampusPage {
  protected readonly money = money;
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly dateTime = dateTime;
  protected readonly data = load(() => this.api.get<OwnCampus>('student/campus'));
  protected readonly busy = signal(false);

  protected ask(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!.value;
    const body = {
      leaves_at: field('out-leaves') ? new Date(field('out-leaves')).toISOString() : '',
      returns_at: field('out-returns') ? new Date(field('out-returns')).toISOString() : '',
      reason: field('out-reason').trim(),
    };
    this.busy.set(true);
    this.api.post('student/campus/out-passes', body).subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show('Sent to the warden.');
        this.data.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
