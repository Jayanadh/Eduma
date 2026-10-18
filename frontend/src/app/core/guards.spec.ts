import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, CanActivateFn, provideRouter, Router, RouterStateSnapshot } from '@angular/router';
import { AuthStore } from './auth-store';
import { guestOnly, memberOnly, platformOnly, requires, signedIn } from './guards';
import { makeMe, makeMember, makeSite, onSite, PLATFORM_ADMIN, signInAs } from './test-data';

const route = {} as ActivatedRouteSnapshot;
const at = (url: string) => ({ url }) as RouterStateSnapshot;

describe('guards', () => {
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    router = TestBed.inject(Router);
  });

  function run(guard: CanActivateFn, url: string): string | true {
    const result = TestBed.runInInjectionContext(() => guard(route, at(url)));
    return result === true ? true : router.serializeUrl(result as ReturnType<Router['parseUrl']>);
  }

  it('sends an anonymous visitor to /login', async () => {
    await signInAs(null);
    expect(run(signedIn, '/console')).toBe('/login');
  });

  it('keeps a user who must change the password on /change-password', async () => {
    await signInAs(makeMe({ must_change_password: true }));
    expect(run(signedIn, '/app')).toBe('/change-password');
    expect(run(signedIn, '/change-password')).toBe(true);
  });

  it('platformOnly admits a platform admin on the platform site', async () => {
    await onSite(makeSite('platform'));
    await signInAs(PLATFORM_ADMIN);
    expect(run(platformOnly, '/console')).toBe(true);
  });

  it('platformOnly sends an institution member home', async () => {
    await onSite(makeSite('institution'));
    await signInAs(makeMe());
    expect(run(platformOnly, '/console')).toBe('/');
  });

  it('memberOnly needs a membership on an institution site', async () => {
    await onSite(makeSite('institution'));
    await signInAs(makeMe());
    expect(run(memberOnly, '/app')).toBe(true);
    await onSite(makeSite('platform'));
    expect(run(memberOnly, '/app')).toBe('/');
  });

  it('guestOnly sends a signed-in platform admin to /console and a member to /app', async () => {
    await onSite(makeSite('platform'));
    await signInAs(PLATFORM_ADMIN);
    expect(run(guestOnly, '/login')).toBe('/console');
    await onSite(makeSite('institution'));
    await signInAs(makeMe());
    expect(run(guestOnly, '/login')).toBe('/app');
  });

  it('guestOnly lets a visitor sign in, but not on an unknown or unavailable site', async () => {
    await onSite(makeSite('institution'));
    await signInAs(null);
    expect(run(guestOnly, '/login')).toBe(true);
    await onSite(null);
    expect(run(guestOnly, '/login')).toBe('/');
    await onSite({ kind: 'institution', mode: 'unavailable', institution: { display_name: 'Aster School' } });
    expect(run(guestOnly, '/login')).toBe('/');
  });

  it('requires sends a member without the permission home', async () => {
    await onSite(makeSite('institution'));
    const teacher = makeMe({
      membership: { kind: 'staff', roles: [], permissions: ['institution.read'], restricted: false, status_reason: '' },
    });
    await signInAs(teacher);
    expect(run(requires('role.manage'), '/app/roles')).toBe('/app');
    await signInAs(makeMe());
    expect(run(requires('role.manage'), '/app/roles')).toBe(true);
  });

  it('requires accepts any one of several permissions', async () => {
    await onSite(makeSite('institution'));
    const approver = makeMe({
      membership: { kind: 'staff', roles: [], permissions: ['configuration.publish'], restricted: false, status_reason: '' },
    });
    await signInAs(approver);
    expect(run(requires(['configuration.edit', 'configuration.publish']), '/app/settings')).toBe(true);
  });

  it('sends each kind of member to its own home', async () => {
    await onSite(makeSite('institution'));
    await signInAs(makeMember('applicant'));
    expect(TestBed.inject(AuthStore).home()).toBe('/apply/applications');
    expect(run(memberOnly, '/app')).toBe('/');
    await signInAs(makeMember('student'));
    expect(TestBed.inject(AuthStore).home()).toBe('/student');
    await signInAs(makeMe());
    expect(TestBed.inject(AuthStore).home()).toBe('/app');
  });
});
