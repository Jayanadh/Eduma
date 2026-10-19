import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors, isProblem } from '../../core/api-error';
import { StudentRecord } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { date, dateTime } from '../../core/format';
import { load } from '../../core/load';
import { UnsavedChanges } from '../../core/unsaved-changes';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { ToastService } from '../../ui/toast';
import { GuardiansSection } from './guardians-section';
import { HistorySection } from './history-section';

/** One student's record: details (correctable with student.update), enrollments, where they came from, their login. */
@Component({
  selector: 'app-student-page',
  imports: [GuardiansSection, HistorySection, LoadError, PageHeader, ReactiveFormsModule, RouterLink],
  template: `
    <div class="page">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as student) {
        <app-page-header eyebrow="Student" [title]="student.number + ' · ' + student.full_name" />
        @if (student.left_on) {
          <div class="notice notice-warning section" role="status">
            Left on {{ date(student.left_on) }}{{ exitReason(student) ? ': ' + exitReason(student) : '' }}
            @if (student.can_reinstate) {
              <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="reinstate(student)">Reinstate</button>
            }
          </div>
        }
        @if (student.can_withdraw) {
          @if (withdrawing()) {
            <form class="card stack withdraw section" [formGroup]="leaving" (ngSubmit)="withdraw(student)" novalidate>
              <h2 class="card-title">Withdraw {{ student.full_name }}</h2>
              <p class="muted small">The record and history stay. The student's login stops working. Fees and refunds are decided separately.</p>
              <div class="field">
                <label for="withdraw-date">Leaving date</label>
                <input id="withdraw-date" type="date" formControlName="effective_on" />
                @if (errors()['effective_on']; as message) { <span class="field-error">{{ message }}</span> }
              </div>
              <div class="field">
                <label for="withdraw-reason">Reason</label>
                <input id="withdraw-reason" formControlName="reason" />
                @if (errors()['reason']; as message) { <span class="field-error">{{ message }}</span> }
              </div>
              <div class="field">
                <label for="withdraw-clearance">Clearance note (optional)</label>
                <textarea id="withdraw-clearance" rows="2" formControlName="clearance_note" placeholder="Books returned, certificates issued…"></textarea>
              </div>
              <div class="form-actions">
                <button type="submit" class="btn btn-danger" [disabled]="busy()">Withdraw</button>
                <button type="button" class="btn btn-secondary" (click)="withdrawing.set(false)">Cancel</button>
              </div>
            </form>
          } @else {
            <div class="section"><button type="button" class="btn btn-secondary btn-sm" (click)="startWithdraw()">Withdraw</button></div>
          }
        }
        <div class="grid-2 section">
          <form class="card stack" [formGroup]="form" (ngSubmit)="save(student)" novalidate>
            <h2 class="card-title">Details</h2>
            @if (conflict()) {
              <div class="notice notice-warning" role="alert">
                Someone changed this record while you were editing.
                <button type="button" class="btn btn-secondary btn-sm" (click)="data.reload()">Reload the latest</button>
              </div>
            }
            <div class="field">
              <label for="student-name">Full name</label>
              <input id="student-name" formControlName="full_name" />
              @if (errors()['full_name']; as message) { <span class="field-error">{{ message }}</span> }
            </div>
            <div class="field">
              <label for="student-dob">Date of birth</label>
              <input id="student-dob" type="date" formControlName="date_of_birth" />
              @if (errors()['date_of_birth']; as message) { <span class="field-error">{{ message }}</span> }
            </div>
            <div class="field">
              <label for="student-phone">Phone</label>
              <input id="student-phone" type="tel" formControlName="phone" />
            </div>
            <div class="field">
              <label for="student-email">Email</label>
              <input id="student-email" type="email" formControlName="email" />
              @if (errors()['email']; as message) { <span class="field-error">{{ message }}</span> }
            </div>
            <div class="field">
              <label for="student-address">Address</label>
              <textarea id="student-address" rows="3" formControlName="address"></textarea>
            </div>
            @if (canEdit()) {
              <div class="form-actions">
                <button type="submit" class="btn btn-primary" [disabled]="busy() || form.pristine">{{ busy() ? 'Saving…' : 'Save' }}</button>
              </div>
            } @else {
              <p class="muted small">Your role can see this record but not correct it.</p>
            }
          </form>
          <div class="stack">
            <section class="card">
              <h2 class="card-title">Enrollment</h2>
              <ul class="plain">
                @for (e of student.enrollments; track $index) {
                  <li>
                    <strong>{{ e.place_label }}</strong> · {{ e.academic_year }}{{ e.campus_name ? ' · ' + e.campus_name : '' }}
                    <span class="muted small">from {{ date(e.entry_date) }}{{ e.exit_date ? ' to ' + date(e.exit_date) : '' }} · {{ e.status }}</span>
                  </li>
                }
              </ul>
            </section>
            <section class="card">
              <h2 class="card-title">Admission</h2>
              <p class="small">Admitted {{ date(student.admitted_on) }}</p>
              @if (student.application; as application) {
                <p class="small">From application
                  <a [routerLink]="['/app/admissions/applications', application.id]">{{ application.number }}</a></p>
              }
            </section>
            <app-guardians-section [student]="student" />
            <section class="card">
              <h2 class="card-title">Sign-in</h2>
              @if (student.login) {
                <p class="small">Login <code>{{ student.login }}</code></p>
                <p class="muted small">{{ student.last_login ? 'Last signed in ' + dateTime(student.last_login) : 'Has not signed in yet.' }}</p>
              } @else {
                <p class="muted small">No login.</p>
              }
            </section>
          </div>
        </div>
        <div class="section"><app-history-section [studentId]="student.id" /></div>
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .plain {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 12px 0 0;
      padding: 0;
      list-style: none;

      span {
        display: block;
      }
    }
  `,
})
export class StudentPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly auth = inject(AuthStore);
  private readonly unsaved = inject(UnsavedChanges);
  protected readonly date = date;
  protected readonly dateTime = dateTime;
  protected readonly canEdit = computed(() => this.auth.can('student.update'));
  protected readonly data = load(
    () => this.api.get<StudentRecord>(`institution/students/${this.id()}`),
    () => this.id(),
  );
  protected readonly form = inject(NonNullableFormBuilder).group({
    full_name: ['', [Validators.required]],
    date_of_birth: [''],
    phone: [''],
    email: ['', [Validators.email]],
    address: [''],
  });
  protected readonly busy = signal(false);
  protected readonly withdrawing = signal(false);
  protected readonly leaving = inject(NonNullableFormBuilder).group({ effective_on: [''], reason: [''], clearance_note: [''] });
  private readonly confirm = inject(ConfirmDialog);
  protected readonly conflict = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  constructor() {
    effect(() => {
      const student = this.data.value();
      if (student) {
        this.form.reset({ ...student, date_of_birth: student.date_of_birth ?? '' });
        this.conflict.set(false);
      }
      if (this.canEdit()) {
        this.form.enable();
      } else {
        this.form.disable();
      }
    });
    this.form.valueChanges.subscribe(() => this.unsaved.dirty.set(this.form.dirty));
  }

  protected save(student: StudentRecord): void {
    if (this.busy()) {
      return;
    }
    const values = this.form.getRawValue();
    this.busy.set(true);
    this.errors.set({});
    this.api
      .patch<StudentRecord>(`institution/students/${student.id}`, {
        ...values,
        date_of_birth: values.date_of_birth || null,
        version: student.version,
      })
      .subscribe({
        next: (updated) => {
          this.busy.set(false);
          this.unsaved.dirty.set(false);
          this.data.value.set(updated);
          this.toasts.show('Details saved.');
        },
        error: (err) => {
          this.busy.set(false);
          this.conflict.set(isProblem(err, 'version_conflict'));
          this.errors.set(fieldErrors(err));
          if (!this.conflict() && !Object.keys(this.errors()).length) {
            this.toasts.show(apiErrorMessage(err), 'danger');
          }
        },
      });
  }

  protected exitReason(student: StudentRecord): string {
    return student.enrollments.find((e) => e.exit_date)?.exit_reason ?? '';
  }

  protected startWithdraw(): void {
    this.leaving.reset({ effective_on: new Date().toLocaleDateString('en-CA'), reason: '', clearance_note: '' });
    this.errors.set({});
    this.withdrawing.set(true);
  }

  private moved(student: StudentRecord, message: string): void {
    this.busy.set(false);
    this.withdrawing.set(false);
    this.data.value.set(student);
    this.toasts.show(message);
  }

  protected withdraw(student: StudentRecord): void {
    this.busy.set(true);
    this.errors.set({});
    this.api
      .post<StudentRecord>(`institution/students/${student.id}/withdraw`, { version: student.version, ...this.leaving.getRawValue() })
      .subscribe({
        next: (updated) => this.moved(updated, `${student.full_name} withdrawn.`),
        error: (err) => {
          this.busy.set(false);
          this.errors.set(fieldErrors(err));
          if (!Object.keys(fieldErrors(err)).length) {
            this.toasts.show(apiErrorMessage(err), 'danger');
            this.data.reload();
          }
        },
      });
  }

  protected async reinstate(student: StudentRecord): Promise<void> {
    const yes = await this.confirm.ask({
      title: `Reinstate ${student.full_name}?`,
      message: 'Their enrollment reopens and their login works again.',
      confirmLabel: 'Reinstate',
    });
    if (!yes) {
      return;
    }
    this.busy.set(true);
    this.api.post<StudentRecord>(`institution/students/${student.id}/reinstate`, { version: student.version }).subscribe({
      next: (updated) => this.moved(updated, `${student.full_name} reinstated.`),
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
        this.data.reload();
      },
    });
  }
}
