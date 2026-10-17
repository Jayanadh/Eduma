import { Component, DestroyRef, inject, input, output, signal } from '@angular/core';
import { Icon } from './icon';

/** Searching starts after this many characters, and again when the box is cleared. */
export const SEARCH_MIN_CHARS = 3;
export const SEARCH_DELAY_MS = 300;

/**
 * A search box that searches as you type: once there are 3 or more characters (after a short pause, so not on every
 * key), and again when it is emptied. No Search button. Emits the trimmed text.
 */
@Component({
  selector: 'app-search-box',
  imports: [Icon],
  template: `
    <div class="field">
      <label [for]="id()">{{ label() }}</label>
      <div class="box">
        <app-icon name="search" [size]="18" />
        <input
          [id]="id()"
          type="search"
          autocomplete="off"
          [placeholder]="placeholder()"
          [value]="text()"
          (input)="typed($any($event.target).value)"
          (keydown.enter)="$event.preventDefault()"
        />
      </div>
      @if (hint()) {
        <span class="field-hint" aria-live="polite">{{ hint() }}</span>
      }
    </div>
  `,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }

    .box {
      position: relative;

      app-icon {
        position: absolute;
        top: 50%;
        left: 14px;
        color: var(--muted);
        transform: translateY(-50%);
        pointer-events: none;
      }

      input {
        padding-left: 42px !important;
      }
    }
  `,
})
export class SearchBox {
  readonly id = input('search');
  readonly label = input('Search');
  readonly placeholder = input('Type at least 3 letters');
  readonly search = output<string>();

  protected readonly text = signal('');
  protected readonly hint = signal('');
  private timer: ReturnType<typeof setTimeout> | undefined;
  private last = '';

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.timer));
  }

  protected typed(value: string): void {
    this.text.set(value);
    clearTimeout(this.timer);
    const query = value.trim();
    if (query.length > 0 && query.length < SEARCH_MIN_CHARS) {
      this.hint.set(`Type ${SEARCH_MIN_CHARS - query.length} more to search`);
      return;
    }
    this.hint.set('');
    this.timer = setTimeout(() => {
      if (query !== this.last) {
        this.last = query;
        this.search.emit(query);
      }
    }, SEARCH_DELAY_MS);
  }
}
