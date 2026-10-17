import { Component, computed, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { apiErrorMessage } from '../../core/api-error';
import { AuthStore } from '../../core/auth-store';
import { NavigationHistory } from '../../core/navigation-history';
import { SiteStore } from '../../core/site-store';
import { Reveal } from '../../ui/reveal';
import { ToastService } from '../../ui/toast';

/** Change your own password; the first sign-in with a password someone else chose comes here before anything else. */
@Component({
  selector: 'app-change-password-page',
  imports: [ReactiveFormsModule, Reveal],
  template: `
    <main class="stage">
      <form class="auth-card" [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <div class="brand">
          @if (site.logoUrl(); as logo) {
            <img [src]="logo" alt="" />
          } @else {
            <span class="wordmark">{{ site.institutionName() }}</span>
          }
        </div>
        <h1>{{ compulsory() ? 'Choose your own password' : 'Change your password' }}</h1>
        @if (compulsory()) {
          <p class="notice notice-info">Choose your own password before you continue.</p>
        }
        <div class="field">
          <label for="current-password">{{ compulsory() ? 'Password you were given' : 'Current password' }}</label>
          <div class="password-field">
            <input #pw1 id="current-password" type="password" formControlName="current" autocomplete="current-password" />
            <app-reveal [for]="pw1" />
          </div>
        </div>
        <div class="field">
          <label for="new-password">New password</label>
          <div class="password-field">
            <input #pw2 id="new-password" type="password" formControlName="next" autocomplete="new-password" />
            <app-reveal [for]="pw2" />
          </div>
          <span class="field-hint">At least 8 characters; not all digits, and not a common password.</span>
        </div>
        <div class="field">
          <label for="confirm-password">New password again</label>
          <div class="password-field">
            <input #pw3 id="confirm-password" type="password" formControlName="confirm" autocomplete="new-password" />
            <app-reveal [for]="pw3" />
          </div>
        </div>
        @if (error()) {
          <p class="error small" role="alert">{{ error() }}</p>
        }
        <div class="form-actions">
          <button type="submit" class="btn btn-primary" [disabled]="busy()">
            {{ busy() ? 'Saving…' : 'Save password' }}
          </button>
          @if (!compulsory()) {
            <button type="button" class="btn btn-ghost" (click)="cancel()">Cancel</button>
          } @else {
            <button type="button" class="btn btn-ghost" (click)="auth.signOut()">Sign out</button>
          }
        </div>
      </form>
    </main>
  `,
  styleUrl: './auth-card.scss',
})
export class ChangePasswordPage {
  protected readonly auth = inject(AuthStore);
  protected readonly site = inject(SiteStore);
  private readonly router = inject(Router);
  private readonly history = inject(NavigationHistory);
  private readonly toasts = inject(ToastService);

  protected readonly form = inject(NonNullableFormBuilder).group({ current: [''], next: [''], confirm: [''] });
  protected readonly busy = signal(false);
  protected readonly error = signal('');
  protected readonly compulsory = computed(() => this.auth.user()?.must_change_password ?? false);

  protected submit(): void {
    if (this.busy()) {
      return;
    }
    const { current, next, confirm } = this.form.getRawValue();
    if (!current || !next || !confirm) {
      this.error.set('Enter your current password, a new password and the confirmation.');
      return;
    }
    if (next !== confirm) {
      this.error.set('The new passwords do not match.');
      return;
    }
    this.error.set('');
    this.busy.set(true);
    this.auth.changePassword(current, next).subscribe({
      next: () => {
        this.toasts.show('Password changed.');
        void this.router.navigateByUrl(this.auth.home());
      },
      error: (err) => {
        this.error.set(apiErrorMessage(err));
        this.busy.set(false);
      },
    });
  }

  protected cancel(): void {
    this.history.back(this.auth.home());
  }
}
