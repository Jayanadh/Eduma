import { Component, computed, inject, input } from '@angular/core';
import { SiteStore } from '../../core/site-store';

/**
 * A page with nothing to do but say why: no Eduma site at this address, or an institution that is temporarily
 * unavailable. No links: there is nowhere to go from here on this address.
 */
@Component({
  selector: 'app-notice-page',
  template: `
    <main class="notice-page">
      <img src="/eduma-logo.png" alt="Eduma" width="96" height="96" />
      <h1>{{ heading() }}</h1>
      <p>{{ text() }}</p>
    </main>
  `,
  styles: `
    .notice-page {
      display: grid;
      min-height: 100dvh;
      place-content: center;
      justify-items: center;
      gap: 16px;
      padding: 32px 16px;
      text-align: center;
    }

    h1 {
      max-width: 22ch;
      font-size: clamp(28px, 5vw, 44px);
      font-weight: 800;
    }

    p {
      max-width: 46ch;
      color: var(--muted);
    }
  `,
})
export class NoticePage {
  readonly kind = input<'not-found' | 'unavailable'>('not-found');
  private readonly site = inject(SiteStore);

  protected readonly heading = computed(() =>
    this.kind() === 'unavailable'
      ? `${this.site.institutionName()} is temporarily unavailable.`
      : 'There is no Eduma site at this address.',
  );
  protected readonly text = computed(() =>
    this.kind() === 'unavailable'
      ? 'Please try again later, or contact the institution directly.'
      : 'Check the address, or ask your institution for its Eduma link.',
  );
}
