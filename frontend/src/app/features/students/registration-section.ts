import { Component, computed, inject, input, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { Offering, Page, Registration, StudentRecord } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ToastService } from '../../ui/toast';
import { RULES } from '../academics/registration-rules';

type Hold = { id: string; kind: string; kind_label: string; reason: string; placed_on: string; placed_by: string; lifted_on: string | null };
type Override = { id: string; rule: string; reason: string; offering: string; expires_on: string; granted_by: string; used: boolean };

const OVERRIDABLE = ['prerequisite', 'not_in_regulation', 'already_passed', 'credit_limit', 'hold', 'window_closed'];

/** A college student's registrations on their record: register for them, holds and overrides (S5C-06..08). */
@Component({
  selector: 'app-registration-section',
  template: `
    <section class="card stack">
      <h2 class="card-title">Registration</h2>
      <ul class="rows">
        @for (r of registrations.value()?.results ?? []; track r.id) {
          <li>
            <span><strong>{{ r.offering.label }}</strong> <span class="muted small meta">{{ r.offering.term }} · {{ r.state_label }}{{ r.reason_code ? ' (' + (rules[r.reason_code] ?? r.reason_code) + ')' : '' }}</span></span>
            @if (manage() && (r.state === 'registered' || r.state === 'waitlisted' || r.state === 'pending_approval')) {
              <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Drop ' + r.offering.label" [disabled]="busy()" (click)="drop(r)">Drop</button>
            }
          </li>
        } @empty {
          <li class="muted small">No registrations.</li>
        }
      </ul>
      @if (manage()) {
        <form id="register-for" class="row" (submit)="$event.preventDefault(); register($any($event.target))">
          <div class="field grow">
            <label for="register-offering">Register for</label>
            <select id="register-offering">
              @for (o of open(); track o.id) { <option [value]="o.id">{{ o.label }} · {{ o.course.title }} · {{ o.term.name }}</option> }
            </select>
          </div>
          <label class="small"><input id="register-waitlist" type="checkbox" /> Waitlist if full</label>
          <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy() || !open().length">Register</button>
        </form>
        @if (refusal(); as m) { <p class="field-error" role="alert">{{ m }}</p> }
      }
      <h3 class="card-title">Holds</h3>
      <ul class="rows">
        @for (h of holds.value() ?? []; track h.id) {
          <li>
            <span>{{ h.kind_label }}: {{ h.reason }} <span class="muted small meta">{{ date(h.placed_on) }} by {{ h.placed_by }}{{ h.lifted_on ? ' · lifted ' + date(h.lifted_on) : '' }}</span></span>
            @if (manage() && !h.lifted_on) {
              <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="lift(h)">Lift</button>
            }
          </li>
        } @empty {
          <li class="muted small">No holds.</li>
        }
      </ul>
      @if (manage()) {
        <form id="place-hold" class="row" (submit)="$event.preventDefault(); hold($any($event.target))">
          <div class="field">
            <label for="hold-kind">Hold</label>
            <select id="hold-kind"><option value="academic">Academic</option><option value="administrative">Administrative</option></select>
          </div>
          <div class="field grow"><label for="hold-reason">Reason</label><input id="hold-reason" /></div>
          <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Place hold</button>
        </form>
      }
      <h3 class="card-title">Overrides</h3>
      <ul class="rows">
        @for (o of overrides.value() ?? []; track o.id) {
          <li><span>{{ o.offering }}: past {{ rules[o.rule] ?? o.rule }} <span class="muted small meta">{{ o.reason }} · {{ o.granted_by }} · until {{ date(o.expires_on) }}{{ o.used ? ' · used' : '' }}</span></span></li>
        } @empty {
          <li class="muted small">None.</li>
        }
      </ul>
      @if (canOverride()) {
        <form id="grant-override" class="row" (submit)="$event.preventDefault(); grant($any($event.target))">
          <div class="field">
            <label for="override-offering">Offering</label>
            <select id="override-offering">
              @for (o of open(); track o.id) { <option [value]="o.id">{{ o.label }}</option> }
            </select>
          </div>
          <div class="field">
            <label for="override-rule">Let them past</label>
            <select id="override-rule">
              @for (rule of overridable; track rule) { <option [value]="rule">{{ rules[rule] }}</option> }
            </select>
          </div>
          <div class="field grow"><label for="override-reason">Reason</label><input id="override-reason" /></div>
          <div class="field"><label for="override-until">Until</label><input id="override-until" type="date" /></div>
          <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Grant</button>
        </form>
      }
    </section>
  `,
  styles: `
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: end;
    }

    .grow {
      flex: 1 1 180px;
    }
  `,
})
export class RegistrationSection {
  readonly student = input.required<StudentRecord>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly auth = inject(AuthStore);
  protected readonly date = date;
  protected readonly rules = RULES;
  protected readonly overridable = OVERRIDABLE;
  protected readonly manage = computed(() => this.auth.can('registration.manage'));
  protected readonly canOverride = computed(() => this.auth.can('registration.override'));
  protected readonly registrations = load(
    () => this.api.get<Page<Registration>>('institution/academics/registrations', { student: this.student().id, page_size: 200 }),
    () => this.student().id,
  );
  protected readonly holds = load(
    () => this.api.get<Hold[]>(`institution/academics/students/${this.student().id}/holds`),
    () => this.student().id,
  );
  protected readonly overrides = load(
    () => this.api.get<Override[]>('institution/academics/overrides', { student: this.student().id }),
    () => this.student().id,
  );
  // shortcut: the first 200 offerings, filtered here to open ones; add an open-offerings filter when terms grow.
  private readonly offerings = load(() => this.api.get<Page<Offering>>('institution/academics/offerings', { page_size: 200 }));
  protected readonly open = computed(() => (this.offerings.value()?.results ?? []).filter((o) => o.status === 'open'));
  protected readonly busy = signal(false);
  protected readonly refusal = signal('');

  private send<T>(path: string, body: object, message: string, after: () => void): void {
    this.busy.set(true);
    this.refusal.set('');
    this.api.post<T>(path, body).subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(message);
        after();
      },
      error: (err) => {
        this.busy.set(false);
        this.refusal.set(apiErrorMessage(err));
      },
    });
  }

  protected register(form: HTMLFormElement): void {
    const offering = form.querySelector<HTMLSelectElement>('#register-offering')!.value;
    const waitlist = form.querySelector<HTMLInputElement>('#register-waitlist')!.checked;
    this.send('institution/academics/registrations', { student: this.student().id, offerings: [offering], waitlist }, 'Registered.', () =>
      this.registrations.reload(),
    );
  }

  protected drop(r: Registration): void {
    this.send(`institution/academics/registrations/${r.id}/drop`, { version: r.version }, `${r.offering.label} dropped.`, () =>
      this.registrations.reload(),
    );
  }

  protected hold(form: HTMLFormElement): void {
    const body = {
      kind: form.querySelector<HTMLSelectElement>('#hold-kind')!.value,
      reason: form.querySelector<HTMLInputElement>('#hold-reason')!.value.trim(),
    };
    this.send(`institution/academics/students/${this.student().id}/holds`, body, 'Hold placed.', () => this.holds.reload());
  }

  protected lift(h: Hold): void {
    this.send(`institution/academics/holds/${h.id}/lift`, {}, 'Hold lifted.', () => this.holds.reload());
  }

  protected grant(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value;
    const body = {
      student: this.student().id,
      offering: field('override-offering'),
      rule: field('override-rule'),
      reason: field('override-reason').trim(),
      expires_on: field('override-until'),
    };
    this.send('institution/academics/overrides', body, 'Override granted.', () => this.overrides.reload());
  }
}
