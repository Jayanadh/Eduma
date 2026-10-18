import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { computed, inject, Service, signal } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, firstValueFrom, map, Observable, of, tap, throwError } from 'rxjs';
import { ToastService } from '../ui/toast';
import { apiErrorMessage } from './api-error';
import { Me } from './api/types';
import { SiteStore } from './site-store';

type SessionResponse = { user: Me | null };

/** The server says nobody is signed in (DRF answers 403 for session auth, 401 for others). */
export function isSessionRefusal(err: unknown): boolean {
  return err instanceof HttpErrorResponse && (err.status === 401 || err.status === 403);
}

/**
 * Who is signed in on this address. Each address (Eduma or an institution) has its own session; the server's session
 * cookie is the source of truth and this holds the last answer.
 */
@Service()
export class AuthStore {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  private readonly site = inject(SiteStore);
  private readonly current = signal<Me | null>(null);
  private sessionCheck: Promise<void> | null = null;

  readonly user = this.current.asReadonly();
  readonly isPlatformAdmin = computed(() => this.current()?.is_platform_admin ?? false);
  readonly isMember = computed(() => this.current()?.membership != null);
  private readonly permissions = computed(() => new Set(this.current()?.membership?.permissions ?? []));
  /** The first role's name for the sidebar: "Teacher / Faculty", or "Staff" with none. */
  readonly roleLabel = computed(() =>
    this.isPlatformAdmin() ? 'Eduma platform admin' : (this.current()?.membership?.roles[0]?.label ?? 'Staff'),
  );
  /** Where this user works: the console on Eduma's address; on an institution's, the workspace for staff, the
   * applications for applicants and the portal for students. */
  readonly home = computed(() => {
    if (this.isPlatformAdmin()) {
      return '/console';
    }
    const kind = this.current()?.membership?.kind;
    return kind === 'applicant' ? '/apply/applications' : kind === 'student' ? '/student' : '/app';
  });
  /** The first word of the name longer than two letters, so "K. Lakshmi" greets as "Lakshmi". */
  readonly firstName = computed(() => {
    const name = this.current()?.full_name ?? '';
    return name.split(' ').filter((part) => part.length > 2)[0] ?? name;
  });

  /** Who the server says is signed in: a user, null for nobody, or undefined when it could not be asked. */
  private async askSession(): Promise<Me | null | undefined> {
    try {
      return (await firstValueFrom(this.http.get<SessionResponse>('/api/v1/session'))).user;
    } catch {
      return undefined;
    }
  }

  /** Whether the signed-in member holds a permission somewhere. For showing things only; the server decides. */
  can(perm: string): boolean {
    return this.permissions().has(perm);
  }

  /** Someone just signed up and was signed in by the server. */
  signedUp(user: Me): void {
    this.current.set(user);
  }

  /** Asks the server who is signed in. At start-up a failed call counts as signed out; it never rejects. */
  async loadSession(): Promise<void> {
    this.current.set((await this.askSession()) ?? null);
  }

  login(username: string, password: string): Observable<Me> {
    return this.http.post<{ user: Me }>('/api/v1/session/login', { username, password }).pipe(
      map((response) => response.user),
      tap((user) => this.current.set(user)),
    );
  }

  /** Forgets the user once the server has ended the session, or has said there is none. */
  logout(): Observable<void> {
    return this.http.post<void>('/api/v1/session/logout', {}).pipe(
      map(() => undefined),
      catchError((err: unknown) => (isSessionRefusal(err) ? of(undefined) : throwError(() => err))),
      tap(() => this.current.set(null)),
    );
  }

  /** Signs out and goes to this address's public page, or says why it could not. */
  signOut(): void {
    this.logout().subscribe({
      next: () => void this.router.navigateByUrl('/'),
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }

  /**
   * Asks the server who the session belongs to now, one check at a time: after an API call is refused with 401/403,
   * and when the window comes back into view. Goes to /login if the session has ended (signed out elsewhere, or the
   * institution was suspended), and home if another tab has signed someone else in.
   */
  recheckSession(): Promise<void> {
    const before = this.current();
    if (!before) {
      return Promise.resolve();
    }
    this.sessionCheck ??= this.askSession()
      .then((now) => {
        if (now === undefined) {
          return; // the server could not be asked (a network blip): nothing is known to have changed
        }
        this.current.set(now);
        if (!now) {
          // The session may have ended because the institution was suspended: learn the site's state again, so
          // /login can send the visitor to the "unavailable" page instead of a sign-in nobody can use.
          void this.site.load().then(() => this.router.navigateByUrl('/login'));
        } else if (now.id !== before.id) {
          void this.router.navigateByUrl(this.home());
        }
      })
      .finally(() => (this.sessionCheck = null));
    return this.sessionCheck;
  }

  changePassword(oldPassword: string, newPassword: string): Observable<void> {
    return this.http
      .post<void>('/api/v1/session/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
      })
      .pipe(
        tap(() => this.current.update((user) => user && { ...user, must_change_password: false })),
        map(() => undefined),
      );
  }
}
