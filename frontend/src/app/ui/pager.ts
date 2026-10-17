import { Component, computed, input, output } from '@angular/core';
import { Icon } from './icon';

/** Previous / next for a paged list (the API's 50 a page). */
@Component({
  selector: 'app-pager',
  imports: [Icon],
  template: `
    @if (pages() > 1) {
      <nav class="pager" aria-label="Pages">
        <button
          type="button"
          class="btn-icon"
          [disabled]="page() <= 1"
          (click)="go.emit(page() - 1)"
          aria-label="Previous page"
        >
          <app-icon name="chevron-left" [size]="18" />
        </button>
        <span class="muted small">Page {{ page() }} of {{ pages() }} · {{ count() }} in all</span>
        <button
          type="button"
          class="btn-icon"
          [disabled]="page() >= pages()"
          (click)="go.emit(page() + 1)"
          aria-label="Next page"
        >
          <app-icon name="chevron-right" [size]="18" />
        </button>
      </nav>
    }
  `,
  styles: `
    .pager {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-top: 16px;
    }
  `,
})
export class Pager {
  readonly page = input.required<number>();
  readonly count = input.required<number>();
  readonly pageSize = input(50);
  readonly go = output<number>();
  protected readonly pages = computed(() => Math.max(1, Math.ceil(this.count() / this.pageSize())));
}
