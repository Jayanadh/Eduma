import { Component, input } from '@angular/core';
import { GallerySection } from '../../../core/api/types';
import { ImageSlot } from '../image-slot';
import { SectionHead } from './section-head';

@Component({
  selector: 'app-gallery-section',
  imports: [ImageSlot, SectionHead],
  template: `
    <div class="wrap">
      <app-section-head [eyebrow]="section().eyebrow" [title]="section().title" [tone]="0" [left]="true" />
      <div class="gallery">
        @for (image of section().images; track $index) {
          <figure class="gallery-item"><app-image-slot [image]="image" [tone]="$index % 3" /></figure>
        }
      </div>
    </div>
  `,
})
export class GallerySectionView {
  readonly section = input.required<GallerySection>();
}
