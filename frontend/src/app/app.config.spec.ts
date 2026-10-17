import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ApplicationInitStatus } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { appConfig } from './app.config';
import { AuthStore } from './core/auth-store';
import { SiteStore } from './core/site-store';
import { makeMe, makeSite } from './core/test-data';

describe('app start-up', () => {
  it('learns the site, then who is signed in, before the first page', async () => {
    TestBed.configureTestingModule({ providers: [...appConfig.providers, provideHttpClientTesting()] });
    const http = TestBed.inject(HttpTestingController);
    const done = TestBed.inject(ApplicationInitStatus).donePromise;
    http.expectOne('/api/v1/public/site').flush(makeSite('institution'));
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/v1/session').flush({ user: makeMe() });
    await done;
    expect(TestBed.inject(SiteStore).kind()).toBe('institution');
    expect(TestBed.inject(AuthStore).user()?.username).toBe('aster.admin');
    http.verify();
  });
});
