import { Component, input } from '@angular/core';
import { FeatureSection } from '../../../core/api/types';
import { Icon } from '../../../ui/icon';
import { ImageSlot } from '../image-slot';
import { CtaLink } from './cta-link';

/** The dark band: a heading, a short text, a few points and an optional picture. */
@Component({
  selector: 'app-feature-section',
  imports: [CtaLink, Icon, ImageSlot],
  template: `
    <div class="wrap feature" [class.with-image]="section().image">
      <div class="feature-text">
        @if (section().eyebrow) {
          <p class="pill-eyebrow tone-1">{{ section().eyebrow }}</p>
        }
        <h2>{{ section().title }}</h2>
        @if (section().text) {
          <p class="lead">{{ section().text }}</p>
        }
        @if (section().bullets.length) {
          <ul class="feature-points">
            @for (point of section().bullets; track $index) {
              <li><app-icon name="check" [size]="18" /> {{ point }}</li>
            }
          </ul>
        }
        @if (section().cta; as cta) {
          <app-cta-link [cta]="cta" />
        }
      </div>
      @if (section().image; as image) {
        <figure class="feature-image"><app-image-slot [image]="image" [tone]="1" /></figure>
      }
    </div>
  `,
})
export class FeatureSectionView {
  readonly section = input.required<FeatureSection>();
}
