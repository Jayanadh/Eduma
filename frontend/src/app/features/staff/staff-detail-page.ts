import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { Assignment, Campus, Department, Page, RoleItem, StaffDetail } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { date, dateTime } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Icon } from '../../ui/icon';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { StatusBadge } from '../../ui/status-badge';
import { ToastService } from '../../ui/toast';
import { ScopePicker, ScopeValue } from './scope-picker';

const ALL = { page_size: 200 };
const WHOLE: ScopeValue = { scope_type: 'institution', campus: null, department: null };

/** Roles in three groups: doing now, starting later, and history. */
export function groupAssignments(rows: readonly Assignment[]) {
  return {
    now: rows.filter((row) => row.in_effect),
    later: rows.filter((row) => !row.in_effect && row.status === 'active' && !isPast(row)),
    past: rows.filter((row) => !row.in_effect && (row.status === 'ended' || isPast(row))),
  };
}

function isPast(row: Assignment): boolean {
  return row.ends_on !== null && row.ends_on < new Date().toISOString().slice(0, 10);
}

/** One member of staff: details, roles (give and end), password reset, removal and restore. What the viewer may not
 * change is not offered; the server checks every change again. */
@Component({
  selector: 'app-staff-detail-page',
  imports: [Icon, LoadError, PageHeader, ReactiveFormsModule, ScopePicker, StatusBadge],
  template: `
    <div class="page">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as person) {
        <app-page-header eyebrow="Staff" [title]="person.full_name" backLink="/app/staff">
          <app-status-badge [status]="person.status === 'active' ? 'active' : 'archived'" [label]="person.status === 'active' ? 'On staff' : 'Removed'" />
        </app-page-header>

        <div class="grid-2 section">
          <section class="card stack">
            <h2 class="card-title">Details</h2>
            @if (person.can_manage) {
              <form class="stack" [formGroup]="details" (ngSubmit)="saveDetails(person)" novalidate>
                <div class="field">
                  <label for="detail-name">Full name</label>
                  <input id="detail-name" formControlName="full_name" />
                  @if (detailErrors()['full_name']; as message) { <span class="field-error">{{ message }}</span> }
                </div>
                <div class="field">
                  <label for="detail-email">Email</label>
                  <input id="detail-email" type="email" formControlName="email" />
                  @if (detailErrors()['email']; as message) { <span class="field-error">{{ message }}</span> }
                </div>
                <div class="field">
                  <label for="detail-mobile">Mobile</label>
                  <input id="detail-mobile" type="tel" formControlName="mobile" />
                </div>
                <div class="form-actions">
                  <button type="submit" class="btn btn-primary" [disabled]="busy() || details.pristine">Save details</button>
                </div>
              </form>
            }
            <dl class="facts">
              <div><dt>Login ID</dt><dd class="url">{{ person.username }}</dd></div>
              @if (!person.can_manage) {
                <div><dt>Email</dt><dd>{{ person.email || '—' }}</dd></div>
              }
              <div>
                <dt>Signed in</dt>
                <dd>
                  {{ person.last_login ? dateTime(person.last_login) : 'Not yet' }}
                  @if (person.must_change_password) { · still on a first password }
                </dd>
              </div>
            </dl>
            @if (person.can_manage) {
              <div class="form-actions">
                @if (person.status === 'active') {
                  <button type="button" class="btn btn-secondary btn-sm" (click)="resetPassword(person)">
                    <app-icon name="key" [size]="16" /> Reset password
                  </button>
                  <button type="button" class="btn btn-secondary btn-sm" (click)="remove(person)">
                    <app-icon name="x-circle" [size]="16" /> Remove from staff
                  </button>
                }
              </div>
            }
            @if (person.status === 'revoked' && auth.can('membership.assign')) {
              <button type="button" class="btn btn-primary btn-sm" (click)="restore(person)">Restore to staff</button>
            }
          </section>

          <section class="card stack">
            <h2 class="card-title">Roles</h2>
            @for (group of groups(); track group.label) {
              @if (group.rows.length) {
                <h3 class="small muted group">{{ group.label }}</h3>
                <ul class="list">
                  @for (row of group.rows; track row.id) {
                    <li class="list-row">
                      <span class="list-main">
                        <span class="list-title">{{ row.role_label }}</span>
                        <span class="muted small">
                          {{ row.scope_label }} · from {{ date(row.starts_on) }}{{ row.ends_on ? ' until ' + date(row.ends_on) : '' }}
                          @if (row.end_reason) { · {{ row.end_reason }} }
                        </span>
                      </span>
                      @if (person.can_manage && row.status === 'active') {
                        <button type="button" class="btn btn-secondary btn-sm" (click)="end(person, row)">End</button>
                      }
                    </li>
                  }
                </ul>
              }
            }
            @if (!person.assignments.length) {
              <p class="muted">No roles yet.</p>
            }

            @if (person.can_manage && person.status === 'active') {
              <!-- A plain form (not a reactive one), so the native submit event is the one to handle. -->
              <form class="stack give" (submit)="$event.preventDefault(); give(person)" novalidate>
                <h3 class="card-title">Give a role</h3>
                <div class="form-grid">
                  <div class="field">
                    <label for="give-role">Role</label>
                    <select id="give-role" (change)="role.set($any($event.target).value)">
                      <option value="">Choose a role</option>
                      @for (option of roles.value()?.results ?? []; track option.id) {
                        <option [value]="option.id" [selected]="option.id === role()">{{ option.label }}</option>
                      }
                    </select>
                    @if (giveErrors()['role']; as message) { <span class="field-error">{{ message }}</span> }
                  </div>
                  <app-scope-picker [campuses]="campuses.value()?.results ?? []" [departments]="departments.value()?.results ?? []" [(value)]="scope" [errors]="giveErrors()" />
                  <div class="field">
                    <label for="give-start">Starts</label>
                    <input id="give-start" type="date" [value]="startsOn()" (change)="startsOn.set($any($event.target).value)" />
                  </div>
                  <div class="field">
                    <label for="give-end">Until (optional)</label>
                    <input id="give-end" type="date" [value]="endsOn()" (change)="endsOn.set($any($event.target).value)" />
                    @if (giveErrors()['ends_on']; as message) { <span class="field-error">{{ message }}</span> }
                  </div>
                </div>
                <div class="form-actions">
                  <button type="submit" class="btn btn-primary" [disabled]="busy() || !role()">Give role</button>
                </div>
              </form>
            }
          </section>
        </div>
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .group {
      margin: 8px 0 0;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .give {
      padding-top: 16px;
      border-top: 1px solid var(--border);
    }
  `,
})
export class StaffDetailPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  protected readonly auth = inject(AuthStore);
  protected readonly date = date;
  protected readonly dateTime = dateTime;

  protected readonly data = load(
    () => this.api.get<StaffDetail>(`institution/staff/${this.id()}`),
    () => this.id(),
  );
  protected readonly roles = load(() => this.api.get<Page<RoleItem>>('institution/roles', { ...ALL, assignable: 1 }));
  protected readonly campuses = load(() => this.api.get<Page<Campus>>('institution/campuses', { ...ALL, active: 1 }));
  protected readonly departments = load(() =>
    this.api.get<Page<Department>>('institution/departments', { ...ALL, active: 1 }),
  );

  protected readonly groups = computed(() => {
    const { now, later, past } = groupAssignments(this.data.value()?.assignments ?? []);
    return [
      { label: 'Now', rows: now },
      { label: 'Starts later', rows: later },
      { label: 'Earlier', rows: past },
    ];
  });

  protected readonly details = inject(NonNullableFormBuilder).group({
    full_name: ['', Validators.required],
    email: [''],
    mobile: [''],
  });
  protected readonly detailErrors = signal<Record<string, string>>({});
  protected readonly role = signal('');
  protected readonly scope = signal<ScopeValue>(WHOLE);
  protected readonly startsOn = signal('');
  protected readonly endsOn = signal('');
  protected readonly giveErrors = signal<Record<string, string>>({});
  protected readonly busy = signal(false);

  constructor() {
    effect(() => {
      const person = this.data.value();
      if (person) {
        this.details.reset({ full_name: person.full_name, email: person.email, mobile: person.mobile });
      }
    });
  }

  /** Every change answers with the person as they now are. */
  private apply(person: StaffDetail, message: string): void {
    this.busy.set(false);
    this.data.value.set(person);
    this.toasts.show(message);
  }

  private refused(err: unknown): void {
    this.busy.set(false);
    this.toasts.show(apiErrorMessage(err), 'danger');
    this.data.reload();
  }

  protected saveDetails(person: StaffDetail): void {
    this.busy.set(true);
    this.detailErrors.set({});
    this.api
      .patch<StaffDetail>(`institution/staff/${person.id}`, { version: person.version, ...this.details.getRawValue() })
      .subscribe({
        next: (updated) => this.apply(updated, 'Details saved.'),
        error: (err) => {
          this.detailErrors.set(fieldErrors(err));
          this.refused(err);
        },
      });
  }

  protected give(person: StaffDetail): void {
    this.busy.set(true);
    this.giveErrors.set({});
    const dates = { starts_on: this.startsOn() || null, ends_on: this.endsOn() || null };
    const body = { role: this.role(), ...this.scope(), ...dates };
    this.api.post<StaffDetail>(`institution/staff/${person.id}/assignments`, body).subscribe({
      next: (updated) => {
        this.role.set('');
        this.scope.set(WHOLE);
        this.startsOn.set('');
        this.endsOn.set('');
        this.apply(updated, 'Role given.');
      },
      error: (err) => {
        const fields = fieldErrors(err);
        this.giveErrors.set(fields);
        this.busy.set(false);
        if (!Object.keys(fields).length) {
          this.toasts.show(apiErrorMessage(err), 'danger');
        }
      },
    });
  }

  protected async end(person: StaffDetail, row: Assignment): Promise<void> {
    const reason = await this.confirm.prompt({
      title: `End ${row.role_label} (${row.scope_label})?`,
      message: `${person.full_name} loses what this role allows on their next action. It stays in their history.`,
      label: 'Reason',
      type: 'textarea',
      required: true,
      hint: 'Kept in the audit log.',
      confirmLabel: 'End role',
      tone: 'danger',
    });
    if (reason === null) {
      return;
    }
    this.busy.set(true);
    this.api.post<StaffDetail>(`institution/staff/${person.id}/assignments/${row.id}/end`, { reason }).subscribe({
      next: (updated) => this.apply(updated, 'Role ended.'),
      error: (err) => this.refused(err),
    });
  }

  protected async resetPassword(person: StaffDetail): Promise<void> {
    const password = await this.confirm.firstPassword(`New first password for ${person.full_name}`);
    if (password === null) {
      return;
    }
    this.api.post<void>(`institution/staff/${person.id}/password`, { password }).subscribe({
      next: () => {
        this.toasts.show('Password set. Hand it over in person; they will choose their own at sign-in.');
        this.data.reload();
      },
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }

  protected async remove(person: StaffDetail): Promise<void> {
    const reason = await this.confirm.prompt({
      title: `Remove ${person.full_name} from staff?`,
      message: 'Their roles end and they are signed out. Their login and history are kept, so they can be restored.',
      label: 'Reason',
      type: 'textarea',
      required: true,
      hint: 'Kept in the audit log.',
      confirmLabel: 'Remove',
      tone: 'danger',
    });
    if (reason === null) {
      return;
    }
    this.busy.set(true);
    this.api
      .post<StaffDetail>(`institution/staff/${person.id}/remove`, { reason, version: person.version })
      .subscribe({ next: (updated) => this.apply(updated, 'Removed from staff.'), error: (err) => this.refused(err) });
  }

  protected restore(person: StaffDetail): void {
    this.busy.set(true);
    this.api
      .post<StaffDetail>(`institution/staff/${person.id}/restore`, { version: person.version })
      .subscribe({
        next: (updated) => this.apply(updated, 'Restored. Give them a role so they can work.'),
        error: (err) => this.refused(err),
      });
  }
}
