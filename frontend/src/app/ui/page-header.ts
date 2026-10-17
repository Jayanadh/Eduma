import { Component, inject, input } from '@angular/core';
import { NavigationHistory } from '../core/navigation-history';
import { Icon } from './icon';

/**
 * Page title with an optional eyebrow, subtitle and Back button. Back returns to the page the person came from, or
 * to `backLink` when the page was opened directly. Projected buttons sit under the title, on the left.
 */
@Component({
  selector: 'app-page-header',
  imports: [Icon],
  template: `
    <header class="page-header">
      <div class="title-row">
        @if (backLink(); as link) {
          <button
            type="button"
            class="btn-icon back"
            aria-label="Back"
            title="Back"
            (click)="history.back(link)"
          >
            <app-icon name="chevron-left" [size]="20" />
          </button>
        }
        <div class="titles">
          @if (eyebrow()) {
            <span class="eyebrow">{{ eyebrow() }}</span>
          }
          <h1 class="page-title">{{ title() }}</h1>
          @if (subtitle()) {
            <p class="muted">{{ subtitle() }}</p>
          }
        </div>
      </div>
      <div class="actions"><ng-content /></div>
    </header>
  `,
  styles: `
    :host {
      display: block;
      margin-bottom: 24px;
    }

    .page-header {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .title-row {
      display: flex;
      align-items: flex-start;
      gap: 14px;
    }

    .back {
      margin-top: 4px;
    }

    .titles {
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-width: 0;
    }

    .titles p {
      max-width: 72ch;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }

    .actions:empty {
      display: none;
    }
  `,
})
export class PageHeader {
  readonly title = input.required<string>();
  readonly eyebrow = input('');
  readonly subtitle = input('');
  /** Where Back goes when there is no earlier page of the app in this tab. */
  readonly backLink = input<string | null>(null);

  protected readonly history = inject(NavigationHistory);
}
