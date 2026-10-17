import { Component, input, signal } from '@angular/core';
import { Icon } from './icon';

/**
 * The eye button that shows or hides a password as it is typed. Put the input and this right after it inside
 * <div class="password-field">, and pass the input: <input #pw type="password" …/><app-reveal [for]="pw" />.
 */
@Component({
  selector: 'app-reveal',
  imports: [Icon],
  template: `
    <button
      type="button"
      class="reveal"
      [attr.aria-label]="shown() ? 'Hide password' : 'Show password'"
      [attr.aria-pressed]="shown()"
      (click)="toggle()"
    >
      <app-icon [name]="shown() ? 'eye-off' : 'eye'" [size]="18" />
    </button>
  `,
})
export class Reveal {
  readonly field = input.required<HTMLInputElement>({ alias: 'for' });
  protected readonly shown = signal(false);

  protected toggle(): void {
    this.shown.update((shown) => !shown);
    this.field().type = this.shown() ? 'text' : 'password';
  }
}
