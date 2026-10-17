import { Component, input } from '@angular/core';
import { PeopleSection } from '../../../core/api/types';
import { ImageSlot } from '../image-slot';
import { SectionHead } from './section-head';

@Component({
  selector: 'app-people-section',
  imports: [ImageSlot, SectionHead],
  template: `
    <div class="wrap">
      <app-section-head [eyebrow]="section().eyebrow" [title]="section().title" [subtitle]="section().subtitle" />
      <ul class="people">
        @for (person of section().items; track $index) {
          <li class="person">
            <app-image-slot class="person-photo" [image]="person.photo" [tone]="$index % 3" icon="user" />
            <h3>{{ person.name }}</h3>
            @if (person.role) {
              <p class="person-role">{{ person.role }}</p>
            }
            @if (person.facts.length) {
              <ul class="person-facts">
                @for (fact of person.facts; track $index) {
                  <li>{{ fact }}</li>
                }
              </ul>
            }
          </li>
        }
      </ul>
    </div>
  `,
})
export class PeopleSectionView {
  readonly section = input.required<PeopleSection>();
}
