import { Component, input } from '@angular/core';
import { HeroSection } from '../../../core/api/types';
import { ImageSlot } from '../image-slot';
import { CtaLink } from './cta-link';

@Component({
  selector: 'app-hero-section',
  imports: [CtaLink, ImageSlot],
  template: `
    <div class="wrap hero">
      @if (section().eyebrow) {
        <p class="pill-eyebrow tone-1">{{ section().eyebrow }}</p>
      }
      <h1 class="hero-title">{{ section().title }}</h1>
      @if (section().subtitle) {
        <p class="hero-subtitle">{{ section().subtitle }}</p>
      }
      @if (!titleOnly()) {
        <div class="hero-actions">
          <app-cta-link [cta]="section().primary_cta" />
          @if (section().secondary_cta; as secondary) {
            <app-cta-link [cta]="secondary" kind="outline" />
          }
        </div>
        @if (section().images.length || section().badge || section().stickers.length) {
          <div class="hero-cards" [class]="'hero-cards count-' + section().images.length">
            @for (image of section().images; track $index) {
              <figure class="hero-card"><app-image-slot [image]="image" [tone]="$index" /></figure>
            }
            @if (section().badge; as badge) {
              <p class="hero-badge">
                <strong>{{ badge.value }}</strong><span>{{ badge.label }}</span>
              </p>
            }
            @for (sticker of section().stickers; track $index) {
              <p [class]="'sticker sticker-' + $index">{{ sticker }}</p>
            }
          </div>
        }
      }
    </div>
  `,
})
export class HeroSectionView {
  readonly section = input.required<HeroSection>();
  /** "Opening soon": the institution's name in its own look, and nothing else yet. */
  readonly titleOnly = input(false);
}
