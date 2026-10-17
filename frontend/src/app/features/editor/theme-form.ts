import { Component, input, output } from '@angular/core';
import { ImageSlot, StoredTheme } from '../../core/api/types';
import { fill, readableOn } from '../../core/contrast';
import { FONT_FAMILIES } from '../../core/site-store';
import { ImagePicker } from './image-picker';

const HEX = /^#[0-9a-f]{6}$/i;
export const HEADING_FONT_LABELS: Readonly<Record<string, string>> = {
  bricolage: 'Bricolage Grotesque',
  fredoka: 'Fredoka',
  jakarta: 'Plus Jakarta Sans',
  'space-grotesk': 'Space Grotesk',
  fraunces: 'Fraunces',
  playfair: 'Playfair Display',
};
export const BODY_FONT_LABELS: Readonly<Record<string, string>> = {
  'dm-sans': 'DM Sans',
  inter: 'Inter',
  nunito: 'Nunito',
  'source-sans': 'Source Sans 3',
  lora: 'Lora',
};
type ColorName = 'primary_color' | 'secondary_color';
type FontName = 'heading_font' | 'body_font';

/** The institution's look: logo, two colours (with the text colour each will get) and two fonts. */
@Component({
  selector: 'app-theme-form',
  imports: [ImagePicker],
  template: `
    <div class="stack">
      <app-image-picker label="Logo" [base]="base()" [slot]="logoSlot()" [describe]="false" (changed)="logoChange.emit($event.asset ? $event : null)" />
      @for (color of colors; track color.name) {
        <div class="field">
          <label [for]="color.name">{{ color.label }}</label>
          <div class="color-row">
            <input type="color" [attr.aria-label]="color.label + ' picker'" [value]="theme()[color.name]" (input)="setColor(color.name, $any($event.target).value)" />
            <input [id]="color.name" class="hex" maxlength="7" [value]="theme()[color.name]" (change)="setColor(color.name, $any($event.target).value, $any($event.target))" />
            <span class="swatch" [style.background]="fillOf(theme()[color.name])" [style.color]="textOn(theme()[color.name])">Aa</span>
          </div>
          <span class="field-hint">
            {{ color.use }} {{ textOn(theme()[color.name]) === '#FFFFFF' ? 'White' : 'Dark' }} text will be used on it.
            @if (adjusted(theme()[color.name])) {
              Behind text it is shown a little darker, so the text stays readable.
            }
          </span>
        </div>
      }
      <div class="form-grid">
        <div class="field">
          <label for="heading-font">Heading font</label>
          <select id="heading-font" (change)="setFont('heading_font', $any($event.target).value)">
            @for (font of headingFonts; track font[0]) {
              <option [value]="font[0]" [selected]="font[0] === theme().heading_font">{{ font[1] }}</option>
            }
          </select>
          <span class="sample" [style.font-family]="family(theme().heading_font)">Headings look like this</span>
        </div>
        <div class="field">
          <label for="body-font">Text font</label>
          <select id="body-font" (change)="setFont('body_font', $any($event.target).value)">
            @for (font of bodyFonts; track font[0]) {
              <option [value]="font[0]" [selected]="font[0] === theme().body_font">{{ font[1] }}</option>
            }
          </select>
          <span class="sample body" [style.font-family]="family(theme().body_font)">Paragraphs look like this.</span>
        </div>
      </div>
    </div>
  `,
  styles: `
    .color-row {
      display: flex;
      align-items: center;
      gap: 10px;

      input[type='color'] {
        flex: none;
        width: 52px;
        height: 46px;
        padding: 2px;
        border: 1.5px solid var(--ink);
        border-radius: 10px;
        background: var(--surface);
        cursor: pointer;
      }

      .hex {
        width: 120px;
        font-family: ui-monospace, Menlo, monospace;
        text-transform: uppercase;
      }
    }

    .swatch {
      display: grid;
      width: 46px;
      height: 46px;
      place-items: center;
      border: 1.5px solid var(--ink);
      border-radius: 10px;
      font-weight: 800;
    }

    .sample {
      font-size: 20px;
      font-weight: 800;

      &.body {
        font-size: 15px;
        font-weight: 400;
      }
    }
  `,
})
export class ThemeForm {
  readonly theme = input.required<StoredTheme>();
  readonly logo = input<{ id: string; url: string } | null>(null);
  readonly base = input.required<string>();
  readonly themeChange = output<{ name: keyof StoredTheme; value: string }>();
  readonly logoChange = output<ImageSlot | null>();

  protected readonly colors: { name: ColorName; label: string; use: string }[] = [
    { name: 'primary_color', label: 'Main colour', use: 'Buttons and links.' },
    { name: 'secondary_color', label: 'Second colour', use: 'Labels, highlights and tiles.' },
  ];
  protected readonly headingFonts = Object.entries(HEADING_FONT_LABELS);
  protected readonly bodyFonts = Object.entries(BODY_FONT_LABELS);

  protected logoSlot(): ImageSlot | null {
    const logo = this.logo();
    return logo ? { asset: logo.id, alt: '' } : { asset: null, alt: '' };
  }

  protected textOn(color: string): string {
    return HEX.test(color) ? readableOn(fill(color)) : '#17132B';
  }

  protected fillOf(color: string): string {
    return HEX.test(color) ? fill(color) : color;
  }

  protected adjusted(color: string): boolean {
    return HEX.test(color) && fill(color) !== color.toUpperCase();
  }

  protected family(code: string): string {
    return FONT_FAMILIES[code] ?? '';
  }

  /** A typed colour that is not #RRGGBB goes back to the current one rather than reaching the page. */
  protected setColor(name: ColorName, value: string, field?: HTMLInputElement): void {
    const color = value.trim().startsWith('#') ? value.trim() : `#${value.trim()}`;
    if (!HEX.test(color)) {
      if (field) {
        field.value = this.theme()[name];
      }
      return;
    }
    this.themeChange.emit({ name, value: color.toUpperCase() });
  }

  protected setFont(name: FontName, value: string): void {
    this.themeChange.emit({ name, value });
  }
}
