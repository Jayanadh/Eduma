import { Component, input } from '@angular/core';
import { ImageSlot as Slot } from '../../core/api/types';
import { Icon } from '../../ui/icon';

/**
 * An image on a public page: the uploaded picture, or, for an empty slot, a tile in one of the brand's soft tones. The
 * empty tile is decoration for visitors; in the editor's preview it also shows what the slot is for.
 */
@Component({
  selector: 'app-image-slot',
  imports: [Icon],
  template: `
    @if (image()?.url; as url) {
      <img [src]="url" [alt]="image()?.alt ?? ''" loading="lazy" />
    } @else {
      <div [class]="'slot-empty tone-' + tone()" aria-hidden="true">
        <app-icon [name]="icon()" [size]="32" />
        @if (image()?.alt; as label) {
          <span class="slot-label">{{ label }}</span>
        }
      </div>
    }
  `,
  host: { class: 'image-slot' },
})
export class ImageSlot {
  readonly image = input<Slot | null>(null);
  readonly tone = input(0);
  readonly icon = input('image');
}
