import { Component, computed, inject } from '@angular/core';
import { SiteStore } from '../../core/site-store';
import { NoticePage } from './notice-page';
import { SiteView } from './site-view';

/** "/" on any address: the Eduma page, an institution's page (or its "opening soon"), or why there is none. */
@Component({
  selector: 'app-landing-page',
  imports: [NoticePage, SiteView],
  template: `
    @if (site(); as site) {
      @if (unavailable()) {
        <app-notice-page kind="unavailable" />
      } @else {
        <app-site-view [site]="site" />
      }
    } @else if (store.failed()) {
      <main class="unreachable">
        <img src="/eduma-logo.png" alt="Eduma" width="96" height="96" />
        <h1>We could not load this page.</h1>
        <p role="alert">The site could not be reached. Check your connection and try again.</p>
        <button type="button" class="btn btn-primary" (click)="store.load()">Try again</button>
      </main>
    } @else {
      <app-notice-page kind="not-found" />
    }
  `,
  styles: `
    .unreachable {
      display: grid;
      min-height: 100dvh;
      place-content: center;
      justify-items: center;
      gap: 16px;
      padding: 32px 16px;
      text-align: center;
    }

    h1 {
      font-size: clamp(26px, 4vw, 40px);
      font-weight: 800;
    }
  `,
})
export class LandingPage {
  protected readonly store = inject(SiteStore);
  protected readonly site = this.store.site;
  protected readonly unavailable = computed(() => {
    const site = this.site();
    return site?.kind === 'institution' && site.mode === 'unavailable';
  });
}
