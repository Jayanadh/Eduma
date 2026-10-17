import { Component, input } from '@angular/core';
import { OfferingsSection } from '../../../core/api/types';
import { ImageSlot } from '../image-slot';
import { CtaLink } from './cta-link';
import { SectionHead } from './section-head';

@Component({
  selector: 'app-offerings-section',
  imports: [CtaLink, ImageSlot, SectionHead],
  template: `
    <div class="wrap">
      <app-section-head [eyebrow]="section().eyebrow" [title]="section().title" [subtitle]="section().subtitle" [tone]="2" />
      <ul class="offer-grid">
        @for (item of section().items; track $index) {
          <li [class]="'offer-card tone-' + ($index % 3)">
            @if (item.image) {
              <app-image-slot class="offer-image" [image]="item.image" [tone]="$index % 3" />
            }
            <h3>{{ item.title }}</h3>
            @if (item.text) {
              <p>{{ item.text }}</p>
            }
            @if (item.tags.length) {
              <ul class="tags">
                @for (tag of item.tags; track $index) {
                  <li>{{ tag }}</li>
                }
              </ul>
            }
            @if (item.cta; as cta) {
              <app-cta-link [cta]="cta" kind="block" />
            }
          </li>
        }
      </ul>
    </div>
  `,
})
export class OfferingsSectionView {
  readonly section = input.required<OfferingsSection>();
}
