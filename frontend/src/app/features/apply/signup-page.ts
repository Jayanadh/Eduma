import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { Me } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { SiteStore } from '../../core/site-store';
import { slugify } from '../../core/slug';
import { Icon } from '../../ui/icon';
import { Reveal } from '../../ui/reveal';

/** A family's own account for applying at this institution. It can apply and nothing else. */
@Component({
  selector: 'app-signup-page',
  imports: [Icon, ReactiveFormsModule, Reveal, RouterLink],
  styleUrl: '../auth/auth-card.scss',
  template: `
    <main class="stage">
      <form class="auth-card" [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <a class="back" routerLink="/apply"><app-icon name="chevron-left" [size]="16" /> Admissions</a>
        <h1>Create an account to apply to {{ site.institutionName() }}</h1>
        <div class="field">
          <label for="signup-name">Your full name</label>
          <input id="signup-name" formControlName="full_name" autocomplete="name" />
          @if (errors()['full_name']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        <div class="field">
          <label for="signup-username">Login ID</label>
          <input id="signup-username" formControlName="username" autocapitalize="none" spellcheck="false" autocomplete="username" />
          <span class="field-hint">You sign in with this. Lowercase letters, digits, dots or dashes.</span>
          @if (errors()['username']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        <div class="field">
          <label for="signup-email">Email (optional)</label>
          <input id="signup-email" type="email" formControlName="email" autocomplete="email" />
          @if (errors()['email']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        <div class="field">
          <label for="signup-phone">Phone (optional)</label>
          <input id="signup-phone" type="tel" formControlName="phone" autocomplete="tel" />
        </div>
        <div class="field">
          <label for="signup-password">Password</label>
          <div class="password-field">
            <input #pw id="signup-password" type="password" formControlName="password" autocomplete="new-password" />
            <app-reveal [for]="pw" />
          </div>
          @if (errors()['password']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        @if (error()) {
          <p class="error" role="alert">{{ error() }}</p>
        }
        <button type="submit" class="btn btn-primary btn-block" [disabled]="busy()">{{ busy() ? 'Creating…' : 'Create account' }}</button>
        <p class="muted small">Already have an account? <a routerLink="/login">Sign in</a></p>
      </form>
    </main>
  `,
})
export class SignupPage {
  private readonly api = inject(Api);
  private readonly auth = inject(AuthStore);
  private readonly router = inject(Router);
  protected readonly site = inject(SiteStore);

  readonly form = inject(NonNullableFormBuilder).group({
    full_name: ['', Validators.required],
    username: ['', Validators.required],
    email: [''],
    phone: [''],
    password: ['', Validators.required],
  });
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');

  constructor() {
    this.form.controls.full_name.valueChanges.pipe(takeUntilDestroyed()).subscribe((name) => {
      if (!this.form.controls.username.dirty) {
        this.form.controls.username.setValue(slugify(name).replaceAll('-', '.'));
      }
    });
  }

  submit(): void {
    if (this.busy()) {
      return;
    }
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    this.api.post<{ user: Me }>('applicant/signup', this.form.getRawValue()).subscribe({
      next: ({ user }) => {
        this.auth.signedUp(user);
        void this.router.navigateByUrl('/apply/applications');
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
