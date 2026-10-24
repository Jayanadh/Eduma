import { Component, computed, inject, signal } from '@angular/core';
import { of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AcademicYear, ClassSection, Offering, Page, RoomT, Subject, Timetable } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

const DAYS = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/** A term's timetable (S6-02..04): a draft with its clashes listed, published when there are none. Rooms too. */
@Component({
  selector: 'app-timetable-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Academics" title="Timetable" subtitle="Weekly lessons per term. Clashes of room, teacher or class block publishing." />
      <div class="field section">
        <label for="tt-term">Term</label>
        <select id="tt-term" (change)="term.set($any($event.target).value)">
          <option value="">Choose a term</option>
          @for (t of terms(); track t.id) { <option [value]="t.id">{{ t.label }}</option> }
        </select>
      </div>
      @if (term()) {
        <app-load-error [message]="versions.error()" (retry)="versions.reload()" />
        <div class="actions section">
          @for (v of versions.value() ?? []; track v.id) {
            <button type="button" class="btn btn-sm" [class.btn-primary]="v.id === current()?.id" [class.btn-secondary]="v.id !== current()?.id" (click)="chosen.set(v.id)">{{ v.number }} · {{ v.status_label }}</button>
          }
          <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="draft()">New draft</button>
        </div>
        @if (current(); as tt) {
          @if (tt.conflicts.length) {
            <div class="notice notice-warning section" role="alert">
              @for (c of tt.conflicts; track $index) { <p class="small">{{ days[c.weekday] }}: {{ c.detail }}</p> }
            </div>
          }
          <div class="card section table-card">
            <table>
              <thead><tr><th>Day</th><th>Time</th><th>Class</th><th>Subject</th><th>Room</th><th>Teacher</th><th><span class="sr-only">Remove</span></th></tr></thead>
              <tbody>
                @for (s of tt.slots; track s.id) {
                  <tr>
                    <td>{{ days[s.weekday] }}</td><td>{{ s.starts_at }}–{{ s.ends_at }}</td><td>{{ s.target.label }}</td>
                    <td>{{ s.subject ?? '' }}</td><td>{{ s.room?.code ?? '' }}</td><td>{{ s.teacher?.full_name ?? '' }}</td>
                    <td>@if (tt.status === 'draft') { <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Remove ' + days[s.weekday] + ' ' + s.starts_at + ' ' + s.target.label" (click)="remove(tt, s.id)">Remove</button> }</td>
                  </tr>
                } @empty {
                  <tr><td colspan="7" class="muted small">No lessons yet.</td></tr>
                }
              </tbody>
            </table>
          </div>
          @if (tt.status === 'draft') {
            <form id="add-slot" class="card stack section" (submit)="$event.preventDefault(); add(tt, $any($event.target))">
              <h2 class="card-title">Add a lesson</h2>
              <div class="grid">
                <div class="field"><label for="slot-day">Day</label>
                  <select id="slot-day">@for (d of [1, 2, 3, 4, 5, 6]; track d) { <option [value]="d">{{ days[d] }}</option> }</select></div>
                <div class="field"><label for="slot-start">Starts</label><input id="slot-start" type="time" value="09:00" /></div>
                <div class="field"><label for="slot-end">Ends</label><input id="slot-end" type="time" value="09:45" /></div>
                <div class="field"><label for="slot-class">Class</label>
                  <select id="slot-class">
                    @for (s of sections.value()?.results ?? []; track s.id) { <option [value]="'section:' + s.id">{{ s.code }} · {{ s.level }}</option> }
                    @for (o of offerings.value()?.results ?? []; track o.id) { <option [value]="'offering:' + o.id">{{ o.label }} · {{ o.course.title }}</option> }
                  </select></div>
                <div class="field"><label for="slot-subject">Subject</label>
                  <select id="slot-subject"><option value="">—</option>@for (s of subjects.value() ?? []; track s.id) { <option [value]="s.id">{{ s.name }}</option> }</select></div>
                <div class="field"><label for="slot-room">Room</label>
                  <select id="slot-room"><option value="">—</option>@for (r of rooms.value() ?? []; track r.id) { <option [value]="r.id">{{ r.code }} · {{ r.name }}</option> }</select></div>
                <div class="field"><label for="slot-teacher">Teacher</label>
                  <select id="slot-teacher"><option value="">—</option>@for (t of staff.value() ?? []; track t.id) { <option [value]="t.id">{{ t.full_name }}</option> }</select></div>
              </div>
              <div class="actions">
                <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add lesson</button>
                <button type="button" class="btn btn-primary btn-sm" [disabled]="busy() || tt.conflicts.length > 0" (click)="publish(tt)">Publish</button>
              </div>
            </form>
          }
        }
      }
      <section class="card stack section">
        <h2 class="card-title">Rooms</h2>
        <p class="small">@for (r of rooms.value() ?? []; track r.id) { <span class="room">{{ r.code }} · {{ r.name }} ({{ r.capacity }})</span> } @empty { <span class="muted">No rooms yet.</span> }</p>
        <form id="add-room" class="row" (submit)="$event.preventDefault(); room($any($event.target))">
          <div class="field"><label for="room-campus">Campus</label>
            <select id="room-campus">@for (c of campuses.value()?.results ?? []; track c.id) { <option [value]="c.id">{{ c.name }}</option> }</select></div>
          <div class="field"><label for="room-code">Code</label><input id="room-code" /></div>
          <div class="field"><label for="room-name">Name</label><input id="room-name" /></div>
          <div class="field"><label for="room-capacity">Seats</label><input id="room-capacity" type="number" min="1" value="40" /></div>
          <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add room</button>
        </form>
      </section>
    </div>
  `,
  styles: `
    .actions,
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: end;
    }

    .grid {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }

    .table-card {
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;

      th,
      td {
        padding: 6px 8px;
        text-align: left;
        border-bottom: 1px solid var(--border);
      }
    }

    .room + .room::before {
      content: ' · ';
    }
  `,
})
export class TimetablePage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly days = DAYS;
  private readonly years = load(() => this.api.get<AcademicYear[]>('institution/academics/years'));
  protected readonly terms = computed(() =>
    (this.years.value() ?? []).filter((y) => y.status !== 'closed').flatMap((y) => y.terms.map((t) => ({ id: t.id, label: `${y.code} ${t.name}` }))),
  );
  protected readonly term = signal('');
  protected readonly chosen = signal('');
  protected readonly versions = load(
    () => (this.term() ? this.api.get<Timetable[]>('institution/academics/timetables', { term: this.term() }) : of([] as Timetable[])),
    () => this.term(),
  );
  protected readonly current = computed(() => {
    const all = this.versions.value() ?? [];
    return all.find((v) => v.id === this.chosen()) ?? all.find((v) => v.status === 'draft') ?? all[0] ?? null;
  });
  protected readonly rooms = load(() => this.api.get<RoomT[]>('institution/academics/rooms'));
  protected readonly sections = load(() => this.api.get<Page<ClassSection>>('institution/academics/sections', { page_size: 200 }));
  protected readonly offerings = load(() => this.api.get<Page<Offering>>('institution/academics/offerings', { page_size: 200 }));
  protected readonly subjects = load(() => this.api.get<Subject[]>('institution/academics/subjects'));
  protected readonly staff = load(() => this.api.get<{ id: string; full_name: string }[]>('institution/academics/staff'));
  protected readonly campuses = load(() => this.api.get<Page<{ id: string; name: string }>>('institution/campuses', { page_size: 200, active: 1 }));
  protected readonly busy = signal(false);

  private run(request: ReturnType<Api['post']>, message: string, after: (t: Timetable) => void = () => this.versions.reload()): void {
    this.busy.set(true);
    request.subscribe({
      next: (result) => {
        this.busy.set(false);
        this.toasts.show(message);
        after(result as Timetable);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected draft(): void {
    this.run(this.api.post<Timetable>('institution/academics/timetables', { term: this.term() }), 'Draft ready.', (t) => {
      this.chosen.set(t.id);
      this.versions.reload();
    });
  }

  protected add(tt: Timetable, form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value;
    const [kind, id] = field('slot-class').split(':');
    const body = {
      weekday: Number(field('slot-day')),
      starts_at: field('slot-start'),
      ends_at: field('slot-end'),
      [kind]: id,
      subject: field('slot-subject') || null,
      room: field('slot-room') || null,
      teacher: field('slot-teacher') || null,
    };
    this.run(this.api.post<Timetable>(`institution/academics/timetables/${tt.id}/slots`, body), 'Lesson added.');
  }

  protected remove(tt: Timetable, slot: string): void {
    this.run(this.api.delete<Timetable>(`institution/academics/timetables/${tt.id}/slots/${slot}`), 'Lesson removed.');
  }

  protected publish(tt: Timetable): void {
    this.run(this.api.post<Timetable>(`institution/academics/timetables/${tt.id}/publish`, { version: tt.version }), 'Timetable published.');
  }

  protected room(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
    const body = { campus: field('room-campus'), code: field('room-code'), name: field('room-name'), capacity: Number(field('room-capacity')) };
    this.run(this.api.post('institution/academics/rooms', body), 'Room added.', () => {
      form.reset();
      this.rooms.reload();
    });
  }
}
