import { Component, input } from '@angular/core';
import { Cta } from '../../../core/api/types';
import { Icon } from '../../../ui/icon';

/** A call to action from page content: a filled or outlined pill with an arrow. */
@Component({
  selector: 'app-cta-link',
  imports: [Icon],
  template: `<a [href]="cta().href" [class]="'cta cta-' + kind()"
    >{{ cta().label }} <app-icon name="arrow-right" [size]="18"
  /></a>`,
})
export class CtaLink {
  readonly cta = input.required<Cta>();
  readonly kind = input<'primary' | 'outline' | 'block'>('primary');
}
