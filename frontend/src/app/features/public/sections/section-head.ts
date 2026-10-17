import { Component, input } from '@angular/core';

/** The pill label and heading that open a section: centred, or on the left beside other content. */
@Component({
  selector: 'app-section-head',
  template: `
    <div class="section-head-public" [class.left]="left()">
      @if (eyebrow()) {
        <p [class]="'pill-eyebrow tone-' + tone()">{{ eyebrow() }}</p>
      }
      <h2>{{ title() }}</h2>
      @if (subtitle()) {
        <p class="lead">{{ subtitle() }}</p>
      }
    </div>
  `,
})
export class SectionHead {
  readonly eyebrow = input('');
  readonly title = input('');
  readonly subtitle = input('');
  readonly tone = input(0);
  readonly left = input(false);
}
