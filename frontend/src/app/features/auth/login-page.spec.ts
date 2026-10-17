import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { PublicSite } from '../../core/api/types';
import { makeMe, makeSite, onSite } from '../../core/test-data';
import { ChangePasswordPage } from './change-password-page';
import { LoginPage } from './login-page';

function type(page: HTMLElement, selector: string, value: string) {
  const input = page.querySelector(selector) as HTMLInputElement;
  input.value = value;
  input.dispatchEvent(new Event('input'));
}

describe('LoginPage', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  async function open(site: PublicSite) {
    await onSite(site);
    const fixture = TestBed.createComponent(LoginPage);
    await fixture.whenStable();
    return fixture;
  }

  it('is the bare Eduma platform sign-in on the main address, with no links', async () => {
    const page = (await open(makeSite('platform'))).nativeElement as HTMLElement;
    expect(page.querySelector('h1')?.textContent).toContain('Eduma platform sign-in');
    expect(page.querySelector('a')).toBeNull();
  });

  it('names the institution on its own address and links back to its page', async () => {
    const page = (await open(makeSite('institution'))).nativeElement as HTMLElement;
    expect(page.querySelector('h1')?.textContent).toContain('Sign in to Aster School');
    expect(page.querySelector('a[href="/"]')).not.toBeNull();
  });

  it('shows a refusal and keeps the typed login ID', async () => {
    const fixture = await open(makeSite('institution'));
    const page = fixture.nativeElement as HTMLElement;
    type(page, '#login-username', 'aster.admin');
    type(page, '#login-password', 'wrong');
    (page.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    http
      .expectOne('/api/v1/session/login')
      .flush(
        { code: 'invalid_credentials', detail: 'Invalid login ID or password.' },
        { status: 400, statusText: 'Bad Request' },
      );
    await fixture.whenStable();
    expect(page.querySelector('[role="alert"]')?.textContent).toContain('Invalid login ID or password.');
    expect((page.querySelector('#login-username') as HTMLInputElement).value).toBe('aster.admin');
  });

  it('goes to the workspace, or to change a first password', async () => {
    const fixture = await open(makeSite('institution'));
    const page = fixture.nativeElement as HTMLElement;
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    type(page, '#login-username', 'aster.admin');
    type(page, '#login-password', 'Demo-pass-2026');
    (page.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    http.expectOne('/api/v1/session/login').flush({ user: makeMe({ must_change_password: true }) });
    await fixture.whenStable();
    expect(navigate).toHaveBeenCalledWith('/change-password');
  });
});

describe('ChangePasswordPage', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  it('says the new passwords differ before sending anything', async () => {
    const fixture = TestBed.createComponent(ChangePasswordPage);
    await fixture.whenStable();
    const page = fixture.nativeElement as HTMLElement;
    type(page, '#current-password', 'Old-pass-2026');
    type(page, '#new-password', 'New-pass-2026');
    type(page, '#confirm-password', 'Other-pass-2026');
    (page.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    expect(page.querySelector('[role="alert"]')?.textContent).toContain('do not match');
    TestBed.inject(HttpTestingController).expectNone('/api/v1/session/change-password');
  });
});
