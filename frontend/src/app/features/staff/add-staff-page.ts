import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { Campus, Department, Page, RoleItem, StaffDetail } from '../../core/api/types';
import { load } from '../../core/load';
import { slugify } from '../../core/slug';
import { PageHeader } from '../../ui/page-header';
import { Reveal } from '../../ui/reveal';
import { ToastService } from '../../ui/toast';
import { ScopePicker, ScopeValue } from './scope-picker';

const ALL = { page_size: 200 };

/** A new login for a member of staff: a first password they must change, and their first role. */
@Component({
  selector: 'app-add-staff-page',
  imports: [PageHeader, ReactiveFormsModule, Reveal, ScopePicker],
  template: `
    <div class="page">
      <app-page-header eyebrow="Staff" title="Add staff" backLink="/app/staff" />
      <form class="card card-strong stack section" [formGroup]="form" (ngSubmit)="save()" novalidate>
        <div class="form-grid">
          <div class="field">
            <label for="staff-name">Full name</label>
            <input id="staff-name" formControlName="full_name" [attr.aria-invalid]="!!errors()['full_name']" />
            @if (errors()['full_name']; as message) { <span class="field-error">{{ message }}</span> }
          </div>
          <div class="field">
            <label for="staff-username">Login ID</label>
            <input id="staff-username" formControlName="username" autocapitalize="none" spellcheck="false" autocomplete="off" [attr.aria-invalid]="!!errors()['username']" />
            @if (errors()['username']; as message) { <span class="field-error">{{ message }}</span> }
          </div>
          <div class="field">
            <label for="staff-email">Email (optional)</label>
            <input id="staff-email" type="email" formControlName="email" autocomplete="off" />
            @if (errors()['email']; as message) { <span class="field-error">{{ message }}</span> }
          </div>
          <div class="field">
            <label for="staff-mobile">Mobile (optional)</label>
            <input id="staff-mobile" type="tel" formControlName="mobile" />
          </div>
          <div class="field full">
            <label for="staff-password">First password</label>
            <div class="password-field">
              <input #pw id="staff-password" type="password" formControlName="password" autocomplete="new-password" [attr.aria-invalid]="!!errors()['password']" />
              <app-reveal [for]="pw" />
            </div>
            <span class="field-hint">Hand it over in person. They must choose their own password the first time they sign in.</span>
            @if (errors()['password']; as message) { <span class="field-error">{{ message }}</span> }
          </div>
          <div class="field">
            <label for="staff-role">Role</label>
            <select id="staff-role" formControlName="role">
              <option value="">Choose a role</option>
              @for (role of roles.value()?.results ?? []; track role.id) {
                <option [value]="role.id">{{ role.label }}</option>
              }
            </select>
            @if (errors()['role']; as message) { <span class="field-error">{{ message }}</span> }
          </div>
          <app-scope-picker [campuses]="campuses.value()?.results ?? []" [departments]="departments.value()?.results ?? []" [(value)]="scope" [errors]="errors()" />
        </div>
        @if (error()) {
          <p class="field-error" role="alert">{{ error() }}</p>
        }
        <div class="form-actions">
          <button type="submit" class="btn btn-primary" [disabled]="busy()">{{ busy() ? 'Adding…' : 'Add staff' }}</button>
        </div>
      </form>
    </div>
  `,
})
export class AddStaffPage {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);

  readonly form = inject(NonNullableFormBuilder).group({
    full_name: ['', Validators.required],
    username: ['', Validators.required],
    email: [''],
    mobile: [''],
    password: ['', Validators.required],
    role: ['', Validators.required],
  });
  protected readonly scope = signal<ScopeValue>({ scope_type: 'institution', campus: null, department: null });
  protected readonly roles = load(() => this.api.get<Page<RoleItem>>('institution/roles', { ...ALL, assignable: 1 }));
  protected readonly campuses = load(() => this.api.get<Page<Campus>>('institution/campuses', { ...ALL, active: 1 }));
  protected readonly departments = load(() =>
    this.api.get<Page<Department>>('institution/departments', { ...ALL, active: 1 }),
  );
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');

  constructor() {
    // The login ID follows the name, "Ravi Kumar" → ravi.kumar, until it is typed by hand.
    this.form.controls.full_name.valueChanges.pipe(takeUntilDestroyed()).subscribe((name) => {
      if (!this.form.controls.username.dirty) {
        this.form.controls.username.setValue(slugify(name).replaceAll('-', '.'));
      }
    });
  }

  protected save(): void {
    if (this.busy()) {
      return;
    }
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    this.api.post<StaffDetail>('institution/staff', { ...this.form.getRawValue(), ...this.scope() }).subscribe({
      next: (person) => {
        this.toasts.show(`${person.full_name} added. Hand over their first password in person.`);
        void this.router.navigate(['/app/staff', person.id], { replaceUrl: true });
      },
      error: (err) => {
        this.busy.set(false);
        const fields = fieldErrors(err);
        this.errors.set(fields);
        if (!Object.keys(fields).length) {
          this.error.set(apiErrorMessage(err));
        }
      },
    });
  }
}
