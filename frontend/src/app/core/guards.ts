import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthStore } from './auth-store';
import { SiteStore } from './site-store';

const CHANGE_PASSWORD_PATH = '/change-password';

function pathOf(url: string): string {
  return url.split(/[?#]/)[0];
}

/**
 * Signed-in users only; anyone else goes to this address's sign-in page. A user who must change a password someone
 * else chose may reach nothing else. Use it as canActivateChild on a shell so it runs on every navigation inside it.
 */
export const signedIn: CanActivateFn = (_route, state) => {
  const user = inject(AuthStore).user();
  const router = inject(Router);
  if (!user) {
    return router.parseUrl('/login');
  }
  if (user.must_change_password && pathOf(state.url) !== CHANGE_PASSWORD_PATH) {
    return router.parseUrl(CHANGE_PASSWORD_PATH);
  }
  return true;
};

/** The console: Eduma's own address, platform admins only. The server checks the same on every call. */
export const platformOnly: CanActivateFn = () =>
  inject(SiteStore).kind() === 'platform' && inject(AuthStore).isPlatformAdmin()
    ? true
    : inject(Router).parseUrl('/');

/** An institution's workspace: its own address, its members only. */
export const memberOnly: CanActivateFn = () =>
  inject(SiteStore).kind() === 'institution' && inject(AuthStore).isMember()
    ? true
    : inject(Router).parseUrl('/');

/** The sign-in page: signed-in users go to their work; addresses where nobody can sign in go to their public page. */
export const guestOnly: CanActivateFn = () => {
  const auth = inject(AuthStore);
  const site = inject(SiteStore).site();
  const router = inject(Router);
  if (auth.user()) {
    return router.parseUrl(auth.home());
  }
  const closed = !site || (site.kind === 'institution' && site.mode === 'unavailable');
  return closed ? router.parseUrl('/') : true;
};
