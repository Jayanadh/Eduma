import { Component, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { date, dateTime } from '../../core/format';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

type HostelT = { id: string; name: string; beds: { id: string; room: string; label: string; resident: string | null }[]; occupied: number; capacity: number };
type AllocationT = { id: string; student: { number: string; full_name: string }; bed: { id: string; room: string; label: string; hostel: string } | null; starts_on: string; ends_on: string; state: string };
type OutPassT = { id: string; student: string; leaves_at: string; returns_at: string; reason: string; state: string };

/** The warden's desk (S10A-08, S10A-09): beds and who is in them, requests to place, transfers and out-passes. */
@Component({
  selector: 'app-hostel-page',
  imports: [PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Campus" title="Hostel" subtitle="A bed holds one resident at a time; a student holds one bed." />
      @for (h of hostels.value() ?? []; track h.id) {
        <section class="card stack section">
          <h2 class="card-title">{{ h.name }} · {{ h.occupied }} of {{ h.capacity }} beds in use</h2>
          <p class="small">@for (b of h.beds; track b.id) { <span class="part">{{ b.room }} {{ b.label }}: {{ b.resident ?? 'free' }}</span> }</p>
        </section>
      }
      <section class="card stack section">
        <h2 class="card-title">Places</h2>
        <ul class="rows">
          @for (a of allocations.value() ?? []; track a.id) {
            <li>
              <span>{{ a.student.full_name }} <span class="muted small">· {{ a.bed ? a.bed.hostel + ' ' + a.bed.room + ' ' + a.bed.label : 'no bed yet' }} · {{ date(a.starts_on) }}–{{ date(a.ends_on) }} · {{ a.state }}</span></span>
              <span class="actions">
                @if (a.state === 'requested') {
                  <label class="sr-only" [for]="'bed-' + a.id">Bed</label>
                  <select [id]="'bed-' + a.id">@for (b of freeBeds(); track b.id) { <option [value]="b.id">{{ b.label }}</option> }</select>
                  <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve ' + a.student.full_name" (click)="approve(a)">Approve</button>
                }
                @if (a.state === 'approved') { <button type="button" class="btn btn-secondary btn-sm" (click)="act(a, 'check-in')">Check in</button> }
                @if (a.state === 'allocated') { <button type="button" class="btn btn-secondary btn-sm" (click)="act(a, 'check-out')">Check out</button> }
              </span>
            </li>
          }
        </ul>
      </section>
      <section class="card stack section">
        <h2 class="card-title">Out-passes</h2>
        <ul class="rows">
          @for (o of outs.value() ?? []; track o.id) {
            <li>
              <span>{{ o.student }} <span class="muted small">· {{ dateTime(o.leaves_at) }} → {{ dateTime(o.returns_at) }} · {{ o.reason }} · {{ o.state }}</span></span>
              <span class="actions">
                @if (o.state === 'requested') {
                  <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Approve out-pass for ' + o.student" (click)="out(o, 'approve')">Approve</button>
                  <button type="button" class="btn btn-secondary btn-sm" (click)="out(o, 'reject')">Reject</button>
                }
                @if (o.state === 'approved') { <button type="button" class="btn btn-secondary btn-sm" (click)="out(o, 'returned')">Back</button> }
              </span>
            </li>
          }
        </ul>
      </section>
    </div>
  `,
  styles: `
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

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
        justify-content: space-between;
        gap: 8px;
      }
    }

    .part + .part::before {
      content: ' · ';
    }
  `,
})
export class HostelPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly dateTime = dateTime;
  protected readonly hostels = load(() => this.api.get<HostelT[]>('institution/campus/hostels'));
  protected readonly allocations = load(() => this.api.get<AllocationT[]>('institution/campus/allocations'));
  protected readonly outs = load(() => this.api.get<OutPassT[]>('institution/campus/out-passes'));

  protected freeBeds(): { id: string; label: string }[] {
    return (this.hostels.value() ?? []).flatMap((h) => h.beds.filter((b) => !b.resident).map((b) => ({ id: b.id, label: `${h.name} ${b.room} ${b.label}` })));
  }

  private run(request: Observable<unknown>, done: string): void {
    request.subscribe({
      next: () => {
        this.toasts.show(done);
        this.hostels.reload();
        this.allocations.reload();
        this.outs.reload();
      },
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }

  protected approve(a: AllocationT): void {
    const bed = (document.getElementById(`bed-${a.id}`) as HTMLSelectElement | null)?.value;
    this.run(this.api.post(`institution/campus/allocations/${a.id}/approve`, { bed }), 'Place approved.');
  }

  protected act(a: AllocationT, action: 'check-in' | 'check-out'): void {
    this.run(this.api.post(`institution/campus/allocations/${a.id}/${action}`, {}), action === 'check-in' ? 'Checked in.' : 'Checked out.');
  }

  protected out(o: OutPassT, action: 'approve' | 'reject' | 'returned'): void {
    this.run(this.api.post(`institution/campus/out-passes/${o.id}/${action}`, {}), 'Done.');
  }

}
