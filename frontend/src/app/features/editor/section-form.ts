import { Component, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Cta, ImageSlot, Section } from '../../core/api/types';
import { Icon } from '../../ui/icon';
import { ImagePicker } from './image-picker';
import { canAdd, emptyImage, listOf, newEntry, STEP_ICON_CHOICES } from './limits';

type Holder = Record<string, unknown>;

/**
 * The fields of one page section. It edits the section object in place (the editor owns it) and says `changed` after
 * every edit, so the editor can mark the draft unsaved and refresh the preview.
 */
@Component({
  selector: 'app-section-form',
  imports: [FormsModule, Icon, ImagePicker],
  templateUrl: './section-form.html',
  styleUrl: './section-form.scss',
})
export class SectionForm {
  readonly section = input.required<Section>();
  readonly base = input.required<string>();
  readonly changed = output();

  protected readonly icons = STEP_ICON_CHOICES;
  protected readonly ratings = [null, 1, 2, 3, 4, 5];

  protected id(name: string, index?: number): string {
    return `${this.section().id}-${name}${index === undefined ? '' : '-' + index}`;
  }

  protected touch(): void {
    this.changed.emit();
  }

  protected canAdd(): boolean {
    return canAdd(this.section());
  }

  protected add(): void {
    if (this.canAdd()) {
      listOf(this.section()).push(newEntry(this.section()));
      this.touch();
    }
  }

  protected remove(index: number): void {
    listOf(this.section()).splice(index, 1);
    this.touch();
  }

  /** Lists edited as text: one entry per line (facts, points) or comma-separated (tags). */
  protected joined(values: string[], separator: string): string {
    return values.join(separator);
  }

  protected split(holder: Holder, key: string, text: string, separator: string, max: number): void {
    holder[key] = text
      .split(separator === ', ' ? ',' : '\n')
      .map((value) => value.trim())
      .filter(Boolean)
      .slice(0, max);
    this.touch();
  }

  protected toggleCta(holder: Holder, key: string): void {
    holder[key] = holder[key] ? null : ({ label: 'Find out more', href: '#s-faq' } satisfies Cta);
    this.touch();
  }

  protected toggleImage(holder: Holder, key: string): void {
    holder[key] = holder[key] ? null : emptyImage();
    this.touch();
  }

  protected setImage(holder: Holder | unknown[], key: string | number, slot: ImageSlot): void {
    (holder as Record<string | number, unknown>)[key] = slot;
    this.touch();
  }

  protected toggleBadge(): void {
    const hero = this.section();
    if (hero.type === 'hero') {
      hero.badge = hero.badge ? null : { value: '', label: '' };
      this.touch();
    }
  }
}
