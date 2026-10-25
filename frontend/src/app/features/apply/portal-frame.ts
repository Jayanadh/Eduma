import { Component, computed, inject, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthStore } from '../../core/auth-store';
import { SiteStore } from '../../core/site-store';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Icon } from '../../ui/icon';

/** The light frame around applicants' and students' pages: the institution, who is signed in, and a way out. */
@Component({
  selector: 'app-portal-frame',
  imports: [Icon, RouterLink, RouterLinkActive],
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
      @if (auth.user()?.membership?.kind === 'guardian') {
        <nav class="portal-nav" aria-label="Family">
          <a routerLink="/family" routerLinkActive="active">Your children</a>
          @if (comms()) { <a routerLink="/family/messages" routerLinkActive="active">Messages</a> }
          @if (services()) { <a routerLink="/cases" routerLinkActive="active">Cases</a> }
          <a routerLink="/apply/applications" routerLinkActive="active">Applications</a>
        </nav>
      }
      @if (auth.user()?.membership?.kind === 'student' && (academics() || attendance() || exams() || fees() || comms() || campus() || services() || careers())) {
        <nav class="portal-nav" aria-label="Student">
          <a routerLink="/student" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Your record</a>
          @if (attendance()) { <a routerLink="/student/assignments" routerLinkActive="active">Assignments</a> }
          @if (exams()) { <a routerLink="/student/results" routerLinkActive="active">Results</a> }
          @if (fees()) { <a routerLink="/student/fees" routerLinkActive="active">Fees</a> }
          @if (comms()) { <a routerLink="/student/classes" routerLinkActive="active">Online classes</a> }
          @if (campus()) { <a routerLink="/student/campus" routerLinkActive="active">Campus</a> }
          @if (careers()) { <a routerLink="/student/careers" routerLinkActive="active">Careers</a> }
          @if (services()) { <a routerLink="/cases" routerLinkActive="active">Cases</a> }
          @if (auth.higher() && academics()) {
            <a routerLink="/student/registration" routerLinkActive="active">Registration</a>
            <a routerLink="/student/progress" routerLinkActive="active">Degree progress</a>
          }
        </nav>
      }
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

    .portal-nav {
      display: flex;
      gap: 16px;

      a {
        color: var(--muted);
        font-weight: 700;
        text-decoration: none;
      }

      a.active {
        color: var(--primary-text, var(--text));
        text-decoration: underline;
        text-underline-offset: 4px;
      }
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
  protected readonly academics = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('academics') ?? false);
  protected readonly campus = computed(() =>
    ['library', 'transport', 'hostel'].some((m) => this.auth.user()?.membership?.modules_enabled?.includes(m)),
  );
  protected readonly services = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('services') ?? false);
  protected readonly careers = computed(() =>
    ['placements', 'quality'].some((m) => this.auth.user()?.membership?.modules_enabled?.includes(m)),
  );
  protected readonly comms = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('communication') ?? false);
  protected readonly fees = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('fees') ?? false);
  protected readonly exams = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('exams') ?? false);
  protected readonly attendance = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('attendance') ?? false);
  private readonly confirm = inject(ConfirmDialog);

  protected async signOut(): Promise<void> {
    const yes = await this.confirm.ask({ title: 'Sign out?', message: 'You can sign in again at any time.', confirmLabel: 'Sign out' });
    if (yes) {
      this.auth.signOut();
    }
  }
}
