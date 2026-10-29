import { Component, computed, DestroyRef, ElementRef, inject, input } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { filter } from 'rxjs';
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
        @if (site.logoUrl(); as logo) {
          <img class="mark" [src]="logo" alt="" width="36" height="36" />
        } @else {
          <span class="mark initials" aria-hidden="true">{{ initials() }}</span>
        }
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
      @if (auth.user()?.membership?.kind === 'student' && (academics() || auth.on('course_registration') || attendance() || exams() || fees() || comms() || campus() || services() || careers())) {
        <nav class="portal-nav" aria-label="Student">
          <a routerLink="/student" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Your record</a>
          @if (attendance()) { <a routerLink="/student/assignments" routerLinkActive="active">Assignments</a> }
          @if (exams()) { <a routerLink="/student/results" routerLinkActive="active">Results</a> }
          @if (fees()) { <a routerLink="/student/fees" routerLinkActive="active">Fees</a> }
          @if (comms()) { <a routerLink="/student/classes" routerLinkActive="active">Online classes</a> }
          @if (campus()) { <a routerLink="/student/campus" routerLinkActive="active">Campus</a> }
          @if (careers()) { <a routerLink="/student/careers" routerLinkActive="active">Careers</a> }
          @if (services()) { <a routerLink="/cases" routerLinkActive="active">Cases</a> }
          @if (auth.higher() && auth.on('course_registration')) {
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
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 16px;
      border-bottom: 1px solid var(--border);
      background: color-mix(in srgb, var(--surface) 88%, transparent);
      backdrop-filter: saturate(1.4) blur(12px);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      margin-right: auto;
      color: inherit;
      text-decoration: none;

      strong {
        overflow: hidden;
        font-family: var(--font-heading);
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .mark {
      flex: none;
      width: 36px;
      height: 36px;
      border-radius: var(--radius-sm);
      object-fit: contain;
    }

    .initials {
      display: grid;
      place-items: center;
      border: 2px solid var(--ink);
      background: var(--brand-primary);
      box-shadow: var(--shadow-hard-sm);
      color: var(--brand-on-primary);
      font-family: var(--font-heading);
      font-size: 14px;
      font-weight: 800;
    }

    .portal-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;

      a {
        display: inline-flex;
        align-items: center;
        min-height: 40px;
        padding: 0 16px;
        border: 1.5px solid var(--border-strong);
        border-radius: var(--radius-pill);
        background: var(--surface);
        color: var(--ink);
        font-weight: 700;
        text-decoration: none;
        white-space: nowrap;
        transition: background-color 0.15s, border-color 0.15s;
      }

      a:hover {
        border-color: var(--ink);
      }

      a.active {
        border-color: var(--ink);
        background: var(--brand-primary);
        box-shadow: var(--shadow-hard-sm);
        color: var(--brand-on-primary);
      }
    }

    /* Phones: one strip to swipe, edge to edge, fading out where more pills wait. */
    @media (max-width: 599px) {
      .portal-nav {
        flex-wrap: nowrap;
        margin: 0 -16px;
        padding: 2px 16px 6px;
        overflow-x: auto;
        scroll-snap-type: x proximity;
        scrollbar-width: none;
        mask-image: linear-gradient(to right, #000 calc(100% - 28px), transparent);

        a {
          scroll-snap-align: start;
        }
      }

      .portal-nav::-webkit-scrollbar {
        display: none;
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
  private readonly host = inject(ElementRef<HTMLElement>);
  /** The institution's initials when it has no logo: "Aster School" → "AS". */
  protected readonly initials = computed(() =>
    this.site
      .institutionName()
      .split(/\s+/)
      .filter((word) => /^[A-Za-z]/.test(word))
      .slice(0, 2)
      .map((word) => word[0].toUpperCase())
      .join(''),
  );

  constructor() {
    // On a phone the current page's pill may be off-screen in the strip: bring it into view after each navigation.
    const reveal = () =>
      requestAnimationFrame(() =>
        this.host.nativeElement.querySelector('.portal-nav a.active')?.scrollIntoView?.({ block: 'nearest', inline: 'center' }),
      );
    const done = inject(Router)
      .events.pipe(filter((event) => event instanceof NavigationEnd))
      .subscribe(reveal);
    inject(DestroyRef).onDestroy(() => done.unsubscribe());
    reveal();
  }

  protected async signOut(): Promise<void> {
    const yes = await this.confirm.ask({ title: 'Sign out?', message: 'You can sign in again at any time.', confirmLabel: 'Sign out' });
    if (yes) {
      this.auth.signOut();
    }
  }
}
