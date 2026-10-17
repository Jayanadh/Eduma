import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { AuthStore } from './auth-store';
import { sessionInterceptor } from './session-interceptor';
import { makeMe, signInAs } from './test-data';

describe('sessionInterceptor', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([sessionInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('rechecks the session when a call is refused, and leaves for /login if it has ended', async () => {
    await signInAs(makeMe());
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    TestBed.inject(HttpClient).get('/api/v1/institution/site/draft').subscribe({ error: () => undefined });
    http
      .expectOne('/api/v1/institution/site/draft')
      .flush({ code: 'authentication_required' }, { status: 403, statusText: 'Forbidden' });
    http.expectOne('/api/v1/session').flush({ user: null });
    await new Promise((resolve) => setTimeout(resolve));
    // The site may have changed too (an institution suspended): ask again before choosing where to go.
    http.expectOne('/api/v1/public/site').flush({ kind: 'institution', mode: 'unavailable', institution: { display_name: 'Aster School' } });
    await new Promise((resolve) => setTimeout(resolve));
    expect(TestBed.inject(AuthStore).user()).toBeNull();
    expect(navigate).toHaveBeenCalledWith('/login');
  });

  it('leaves the public and session calls alone', async () => {
    await signInAs(makeMe());
    TestBed.inject(HttpClient).get('/api/v1/public/site').subscribe({ error: () => undefined });
    http.expectOne('/api/v1/public/site').flush({}, { status: 403, statusText: 'Forbidden' });
    http.expectNone('/api/v1/session');
  });
});
