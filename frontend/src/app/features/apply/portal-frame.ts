import { Component, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthStore } from '../../core/auth-store';
import { SiteStore } from '../../core/site-store';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Icon } from '../../ui/icon';

/** The light frame around applicants' and students' pages: the institution, who is signed in, and a way out. */
@Component({
  selector: 'app-portal-frame',
  imports: [Icon, RouterLink],
  template: `
    <header class="portal-bar">
      <a class="brand" routerLink="/">
        @if (site.logoUrl(); as logo) { <img [src]="logo" alt="" width="32" height="32" /> }
        <strong>{{ site.institutionName() }}</strong>
      </a>
      <span class="who muted small">{{ auth.user()?.full_name }}</span>
      <a class="btn-icon" routerLink="/change-password" aria-label="Change password"><app-icon name="key" [size]="18" /></a>
      <button type="button" class="btn btn-secondary btn-sm" (click)="signOut()">Sign out</button>
    </header>
    <main class="portal">
      <h1 class="page-title">{{ heading() }}</h1>
      <ng-content />
    </main>
  `,
  styles: `
    :host {
      display: block;
      min-height: 100vh;
      background: var(--surface-2);
    }

    .portal-bar {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 16px;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-right: auto;
      color: inherit;
      text-decoration: none;
    }

    .portal {
      display: flex;
      flex-direction: column;
      gap: 16px;
      max-width: 860px;
      margin: 0 auto;
      padding: 24px 16px 48px;
    }

    @media (max-width: 480px) {
      .who {
        display: none;
      }
    }
  `,
})
export class PortalFrame {
  readonly heading = input.required<string>();
  protected readonly auth = inject(AuthStore);
  protected readonly site = inject(SiteStore);
  private readonly confirm = inject(ConfirmDialog);

  protected async signOut(): Promise<void> {
    const yes = await this.confirm.ask({ title: 'Sign out?', message: 'You can sign in again at any time.', confirmLabel: 'Sign out' });
    if (yes) {
      this.auth.signOut();
    }
  }
}
