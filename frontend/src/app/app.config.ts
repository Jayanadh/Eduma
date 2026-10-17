import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import {
  provideRouter,
  TitleStrategy,
  withComponentInputBinding,
  withInMemoryScrolling,
} from '@angular/router';
import { routes } from './app.routes';
import { AuthStore } from './core/auth-store';
import { sessionInterceptor } from './core/session-interceptor';
import { SiteStore } from './core/site-store';
import { SiteTitleStrategy } from './core/site-title';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(
      routes,
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'top', anchorScrolling: 'enabled' }),
    ),
    { provide: TitleStrategy, useClass: SiteTitleStrategy },
    provideHttpClient(withInterceptors([sessionInterceptor])),
    // Before the first navigation: which site this address serves (and its theme), then who is signed in here.
    // Both are injected up front: inject() works only before the first await.
    provideAppInitializer(async () => {
      const site = inject(SiteStore);
      const auth = inject(AuthStore);
      await site.load();
      await auth.loadSession();
    }),
  ],
};
