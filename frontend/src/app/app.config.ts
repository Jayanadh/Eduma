import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';
import { routes } from './app.routes';
import { AuthStore } from './core/auth-store';
import { sessionInterceptor } from './core/session-interceptor';
import { SiteStore } from './core/site-store';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(
      routes,
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'top', anchorScrolling: 'enabled' }),
    ),
    provideHttpClient(withInterceptors([sessionInterceptor])),
    // Before the first navigation: which site this address serves (and its theme), then who is signed in here.
    provideAppInitializer(async () => {
      await inject(SiteStore).load();
      await inject(AuthStore).loadSession();
    }),
  ],
};
