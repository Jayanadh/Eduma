import { Component, input } from '@angular/core';
import { StepsSection } from '../../../core/api/types';
import { Icon } from '../../../ui/icon';
import { SectionHead } from './section-head';

/** The content's step icon names → the icon set's names. */
const STEP_ICONS: Readonly<Record<string, string>> = {
  apply: 'clipboard',
  calendar: 'calendar',
  chat: 'message',
  book: 'book',
  check: 'check',
  star: 'star',
  users: 'users',
  home: 'home',
  award: 'award',
  map: 'map',
};

@Component({
  selector: 'app-steps-section',
  imports: [Icon, SectionHead],
  template: `
    <div class="wrap">
      <app-section-head [eyebrow]="section().eyebrow" [title]="section().title" [tone]="1" />
      <ol class="steps" [style.--steps]="section().items.length">
        @for (item of section().items; track $index) {
          <li>
            <span [class]="'step-icon tone-' + ($index % 3)"
              ><app-icon [name]="icon(item.icon)" [size]="26"
            /></span>
            <h3>{{ item.title }}</h3>
            @if (item.text) {
              <p>{{ item.text }}</p>
            }
          </li>
        }
      </ol>
    </div>
  `,
})
export class StepsSectionView {
  readonly section = input.required<StepsSection>();
  protected icon(name: string): string {
    return STEP_ICONS[name] ?? 'check';
  }
}
