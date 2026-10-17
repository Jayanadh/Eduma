import { booleanAttribute, Component, inject, input } from '@angular/core';
import { Icon } from './icon';
import { ToastService } from './toast';

/** An institution's web address as text, with Copy (to hand it over) and, optionally, Open in a new tab. */
@Component({
  selector: 'app-copy-url',
  imports: [Icon],
  template: `
    <span class="url">{{ url() }}</span>
    <button type="button" class="btn-icon small" [attr.aria-label]="'Copy ' + url()" title="Copy" (click)="copy()">
      <app-icon name="copy" [size]="16" />
    </button>
    @if (open()) {
      <a class="btn-icon small" [href]="url()" target="_blank" rel="noopener" aria-label="Open in a new tab" title="Open">
        <app-icon name="external" [size]="16" />
      </a>
    }
  `,
  styles: `
    :host {
      display: inline-flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
      min-width: 0;
    }

    .small {
      width: 36px;
      height: 36px;
    }
  `,
})
export class CopyUrl {
  readonly url = input.required<string>();
  readonly open = input(false, { transform: booleanAttribute });
  private readonly toasts = inject(ToastService);

  protected copy(): void {
    navigator.clipboard.writeText(this.url()).then(
      () => this.toasts.show('Address copied.'),
      () => this.toasts.show('Could not copy. Select the address and copy it yourself.', 'danger'),
    );
  }
}
