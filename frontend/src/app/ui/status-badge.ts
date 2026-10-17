import { Component, computed, input } from '@angular/core';
import { readable } from '../core/format';

type BadgeTone = 'success' | 'warning' | 'danger' | 'info' | 'muted' | 'dark';

const TONES: Readonly<Record<string, BadgeTone>> = {
  active: 'success',
  published: 'success',
  setup: 'info',
  draft: 'info',
  suspended: 'warning',
  archived: 'muted',
  superseded: 'muted',
};

const LABELS: Readonly<Record<string, string>> = {
  setup: 'Setting up',
  superseded: 'Earlier version',
};

@Component({
  selector: 'app-status-badge',
  template: `<span [class]="classes()">{{ text() }}</span>`,
  styles: `
    :host {
      display: inline-flex;
    }
  `,
})
export class StatusBadge {
  readonly status = input.required<string>();
  readonly label = input<string>();

  protected readonly classes = computed(() => {
    const status = this.status();
    return `badge badge-${Object.hasOwn(TONES, status) ? TONES[status] : 'muted'}`;
  });

  protected readonly text = computed(() => {
    const status = this.status();
    return this.label() || (Object.hasOwn(LABELS, status) ? LABELS[status] : readable(status));
  });
}
