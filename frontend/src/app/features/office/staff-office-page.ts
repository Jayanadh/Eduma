import { Component, inject, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { LeaveKind } from './leave-page';
import { OFFICE_STYLES } from './office-styles';

type DayRow = { id: string; number: string; name: string; status: 'present' | 'absent' | 'half_day' | 'on_leave' | null };

const MARKS = [
  ['present', 'Present'],
  ['absent', 'Absent'],
  ['half_day', 'Half day'],
] as const;

/** HR's desk (S10B-01, S10B-02): leave types and the staff attendance register; approved leave shows by itself. */
@Component({
  selector: 'app-staff-office-page',
  imports: [PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="People" title="Staff office" subtitle="Leave types and staff attendance." />
      <section class="card stack section">
        <h2 class="card-title">Staff attendance</h2>
        <div class="field"><label for="att-date">Day</label><input id="att-date" type="date" [value]="day()" (change)="day.set($any($event.target).value)" /></div>
        <ul class="rows">
          @for (p of sheet.value() ?? []; track p.id) {
            <li>
              <span>{{ p.name }} <span class="muted small">{{ p.number }}</span></span>
              @if (p.status === 'on_leave') {
                <span class="muted small">On leave</span>
              } @else {
                <span>
                  <label class="sr-only" [for]="'mark-' + p.id">Attendance for {{ p.name }}</label>
                  <select [id]="'mark-' + p.id" class="mark" [attr.data-employee]="p.id">
                    <option value="" [selected]="!p.status">Not recorded</option>
                    @for (m of marks; track m[0]) { <option [value]="m[0]" [selected]="p.status === m[0]">{{ m[1] }}</option> }
                  </select>
                </span>
              }
            </li>
          } @empty {
            <li class="muted small">No staff have employee records yet.</li>
          }
        </ul>
        <button type="button" id="save-attendance" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="save()">Save attendance</button>
      </section>
      <section class="card stack section">
        <h2 class="card-title">Leave types</h2>
        <ul class="rows">
          @for (k of kinds.value() ?? []; track k.id) {
            <li><span><strong>{{ k.code }}</strong> {{ k.name }}</span><span class="muted small">{{ k.days_per_year }} days a year · {{ k.paid ? 'paid' : 'unpaid' }}</span></li>
          }
        </ul>
        <form id="add-type" class="row" (submit)="$event.preventDefault(); add($any($event.target))">
          <div class="field"><label for="type-code">Code</label><input id="type-code" maxlength="10" required /></div>
          <div class="field grow"><label for="type-name">Name</label><input id="type-name" maxlength="60" required /></div>
          <div class="field"><label for="type-days">Days a year</label><input id="type-days" type="number" min="0" max="366" required /></div>
          <label class="check"><input id="type-unpaid" type="checkbox" /> Unpaid</label>
          <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add type</button>
        </form>
      </section>
    </div>
  `,
  styles: [OFFICE_STYLES],
})
export class StaffOfficePage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly marks = MARKS;
  protected readonly day = signal(new Date().toLocaleDateString('en-CA'));
  protected readonly sheet = load(
    () => this.api.get<DayRow[]>('institution/hr/attendance', { date: this.day() }),
    () => this.day(),
  );
  protected readonly kinds = load(() => this.api.get<LeaveKind[]>('institution/hr/leave-types'));
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        this.sheet.reload();
        this.kinds.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected save(): void {
    const marks = [...document.querySelectorAll<HTMLSelectElement>('select.mark')]
      .filter((s) => s.value)
      .map((s) => ({ employee: s.dataset['employee'], status: s.value }));
    this.run(this.api.post('institution/hr/attendance', { date: this.day(), marks }), 'Attendance saved.');
  }

  protected add(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!;
    const body = {
      code: field('type-code').value.trim(),
      name: field('type-name').value.trim(),
      days_per_year: Number(field('type-days').value),
      paid: !field('type-unpaid').checked,
    };
    this.run(this.api.post('institution/hr/leave-types', body), 'Leave type added.', () => form.reset());
  }
}
