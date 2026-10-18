import { Component, computed, input, model } from '@angular/core';
import { ModuleInfo } from '../../core/api/types';
import { tick, untick } from '../../core/modules';

const GROUPS = [
  { key: 'core', label: 'Core' },
  { key: 'operations', label: 'Operations' },
] as const;

/** Checkboxes for the modules an institution's plan includes. Ticking one ticks what it needs; unticking one unticks
 * what needs it, so the list the server receives is always consistent. */
@Component({
  selector: 'app-module-picker',
  template: `
    @for (group of groups(); track group.key) {
      <fieldset class="modules">
        <legend>{{ group.label }}</legend>
        @for (module of group.items; track module.key) {
          <label class="module">
            <input
              type="checkbox"
              [checked]="selected().includes(module.key)"
              [disabled]="disabled()"
              (change)="toggle(module.key, $any($event.target).checked)"
            />
            <span>
              <strong>{{ module.label }}</strong>
              @if (module.depends_on.length) {
                <span class="muted small needs">Needs {{ labels(module.depends_on) }}</span>
              }
            </span>
          </label>
        }
      </fieldset>
    }
  `,
  styles: `
    :host {
      display: grid;
      gap: 16px;
    }

    .modules {
      display: grid;
      gap: 4px 16px;
      margin: 0;
      padding: 0;
      border: 0;

      @media (min-width: 720px) {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    legend {
      margin-bottom: 8px;
      font-weight: 800;
    }

    .module {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      min-height: 44px;
      padding: 8px 0;
      cursor: pointer;

      input {
        flex: none;
        width: 20px;
        height: 20px;
        margin-top: 2px;
      }
    }

    .needs {
      display: block;
    }
  `,
})
export class ModulePicker {
  readonly catalogue = input.required<ModuleInfo[]>();
  readonly selected = model.required<string[]>();
  readonly disabled = input(false);

  protected readonly groups = computed(() =>
    GROUPS.map((group) => ({ ...group, items: this.catalogue().filter((module) => module.group === group.key) })),
  );

  protected toggle(key: string, on: boolean): void {
    const catalogue = this.catalogue();
    this.selected.set(on ? tick(this.selected(), key, catalogue) : untick(this.selected(), key, catalogue));
  }

  protected labels(keys: string[]): string {
    return keys.map((key) => this.catalogue().find((module) => module.key === key)?.label ?? key).join(', ');
  }
}
