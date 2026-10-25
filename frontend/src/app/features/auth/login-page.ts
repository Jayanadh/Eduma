import { Component, computed, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/api-error';
import { AuthStore } from '../../core/auth-store';
import { SiteStore } from '../../core/site-store';
import { Icon } from '../../ui/icon';
import { Reveal } from '../../ui/reveal';

/**
 * Sign-in for whoever this address belongs to. On Eduma's own address it is the platform sign-in, linked from nowhere;
 * on an institution's address it carries the institution's name and look and admits only its members.
 */
@Component({
  selector: 'app-login-page',
  imports: [Icon, ReactiveFormsModule, Reveal, RouterLink],
  template: `
    <main class="stage">
      <form class="auth-card" [formGroup]="form" (ngSubmit)="submit()" novalidate>
        @if (institution(); as name) {
          <a class="back" routerLink="/"><app-icon name="chevron-left" [size]="16" /> {{ name }}</a>
        }
        <div class="brand">
          @if (site.logoUrl(); as logo) {
            <img [src]="logo" alt="" />
          } @else if (!institution()) {
            <!-- An institution's name is already in the heading; the wordmark is for Eduma's own sign-in. -->
            <span class="wordmark">{{ site.institutionName() }}</span>
          }
        </div>
        <h1>{{ institution() ? 'Sign in to ' + institution() : 'Eduma platform sign-in' }}</h1>
        <div class="field">
          <label for="login-username">Login ID</label>
          <input
            id="login-username"
            type="text"
            formControlName="username"
            autocomplete="username"
            autocapitalize="none"
            autocorrect="off"
            spellcheck="false"
          />
        </div>
        <div class="field">
          <label for="login-password">Password</label>
          <div class="password-field">
            <input #pw id="login-password" type="password" formControlName="password" autocomplete="current-password" />
            <app-reveal [for]="pw" />
          </div>
        </div>
        @if (error()) {
          <p class="error small" role="alert">{{ error() }}</p>
        }
        <button type="submit" class="btn btn-primary btn-block" [disabled]="busy()">
          {{ busy() ? 'Signing in…' : 'Sign in' }}
          <app-icon name="arrow-right" [size]="18" />
        </button>
        <p class="small muted">
          First time here? Sign in with the password you were given; you will then choose your own.
        </p>
      </form>
    </main>
  `,
  styleUrl: './auth-card.scss',
})
export class LoginPage {
  private readonly auth = inject(AuthStore);
  private readonly router = inject(Router);
  protected readonly site = inject(SiteStore);

  protected readonly institution = computed(() =>
    this.site.kind() === 'institution' ? this.site.institutionName() : null,
  );
  protected readonly form = inject(NonNullableFormBuilder).group({ username: [''], password: [''] });
  protected readonly busy = signal(false);
  protected readonly error = signal('');

  protected submit(): void {
    if (this.busy()) {
      return;
    }
    const { username, password } = this.form.getRawValue();
    if (!username.trim() || !password) {
      this.error.set('Enter your login ID and password.');
      return;
    }
    this.error.set('');
    this.busy.set(true);
    this.auth.login(username.trim(), password).subscribe({
      next: (user) =>
        void this.router.navigateByUrl(user.must_change_password ? '/change-password' : this.auth.home()),
      error: (err) => {
        this.error.set(apiErrorMessage(err));
        this.form.controls.password.reset();
        this.busy.set(false);
      },
    });
  }
}
