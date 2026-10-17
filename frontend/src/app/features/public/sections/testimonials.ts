import { Component, input } from '@angular/core';
import { TestimonialsSection } from '../../../core/api/types';
import { ImageSlot } from '../image-slot';
import { SectionHead } from './section-head';

@Component({
  selector: 'app-testimonials-section',
  imports: [ImageSlot, SectionHead],
  template: `
    <div class="wrap">
      <app-section-head [eyebrow]="section().eyebrow" [title]="section().title" [tone]="2" />
      <ul class="notes">
        @for (note of section().items; track $index) {
          <li [class]="'note tone-' + ($index % 3)">
            @if (note.rating) {
              <p class="stars" [attr.aria-label]="note.rating + ' out of 5'">{{ stars(note.rating) }}</p>
            }
            <blockquote>{{ note.quote }}</blockquote>
            <p class="note-by">
              @if (note.photo?.url) {
                <app-image-slot class="note-photo" [image]="note.photo" />
              }
              <span><strong>{{ note.name }}</strong>
                @if (note.relation) {
                  <span>{{ note.relation }}</span>
                }
              </span>
            </p>
          </li>
        }
      </ul>
    </div>
  `,
})
export class TestimonialsSectionView {
  readonly section = input.required<TestimonialsSection>();
  protected stars(rating: number): string {
    return '★'.repeat(rating);
  }
}
