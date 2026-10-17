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
    } @else {
      <app-notice-page kind="not-found" />
    }
  `,
})
export class LandingPage {
  protected readonly site = inject(SiteStore).site;
  protected readonly unavailable = computed(() => {
    const site = this.site();
    return site?.kind === 'institution' && site.mode === 'unavailable';
  });
}
