import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { tap } from 'rxjs';
import { AuthStore, isSessionRefusal } from './auth-store';

const UNWATCHED = ['/api/v1/session', '/api/v1/public/'];

/**
 * When an API call is refused with 401/403, finds out whether the session has ended (signed out, or the institution
 * was suspended) or now belongs to someone else (see AuthStore.recheckSession). The session and public endpoints answer
 * for themselves and are left alone.
 */
export const sessionInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthStore);
  const watched = req.url.startsWith('/api/v1/') && !UNWATCHED.some((prefix) => req.url.startsWith(prefix));
  return next(req).pipe(
    tap({
      error: (err: unknown) => {
        if (watched && isSessionRefusal(err)) {
          void auth.recheckSession();
        }
      },
    }),
  );
};
