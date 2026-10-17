import { Component, input } from '@angular/core';
import { FaqSection } from '../../../core/api/types';
import { CtaLink } from './cta-link';
import { SectionHead } from './section-head';

@Component({
  selector: 'app-faq-section',
  imports: [CtaLink, SectionHead],
  template: `
    <div class="wrap faq">
      <div class="faq-intro">
        <app-section-head [eyebrow]="section().eyebrow" [title]="section().title" [subtitle]="section().subtitle" [tone]="1" [left]="true" />
        @if (section().cta; as cta) {
          <app-cta-link [cta]="cta" kind="outline" />
        }
      </div>
      <div class="faq-list">
        @for (item of section().items; track $index) {
          <details [open]="$first">
            <summary>{{ item.q }}</summary>
            <p>{{ item.a }}</p>
          </details>
        }
      </div>
    </div>
  `,
})
export class FaqSectionView {
  readonly section = input.required<FaqSection>();
}
