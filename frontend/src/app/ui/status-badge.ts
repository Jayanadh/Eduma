import { Component, computed, input } from '@angular/core';
import { readable } from '../core/format';

type BadgeTone = 'success' | 'warning' | 'danger' | 'info' | 'muted' | 'dark';

const TONES: Readonly<Record<string, BadgeTone>> = {
  active: 'success',
  published: 'success',
  setup: 'info',
  draft: 'info',
  suspended: 'warning',
  restricted: 'warning',
  archived: 'muted',
  superseded: 'muted',
  ok: 'success',
  warning: 'warning',
  failing: 'danger',
  unknown: 'muted',
  not_configured: 'muted',
  open: 'danger',
  acknowledged: 'warning',
  resolved: 'muted',
  // Requests, cases, payroll, purchasing and placements: waiting is info, done is success, stopped is muted.
  submitted: 'info',
  requested: 'info',
  assigned: 'info',
  shortlisted: 'info',
  prepared: 'info',
  validated: 'info',
  ordered: 'info',
  pending: 'warning',
  appealed: 'warning',
  offered: 'warning',
  returned: 'warning',
  maintenance: 'warning',
  partially_received: 'warning',
  approved: 'success',
  accepted: 'success',
  received: 'success',
  exported: 'success',
  in_use: 'success',
  rejected: 'muted',
  declined: 'muted',
  withdrawn: 'muted',
  canceled: 'muted',
  disposed: 'muted',
  // Fees: invoices and payments.
  issued: 'warning',
  partially_paid: 'warning',
  paid: 'success',
  succeeded: 'success',
  failed: 'danger',
  expired: 'muted',
  cancelled: 'muted',
};

const LABELS: Readonly<Record<string, string>> = {
  setup: 'Setting up',
  superseded: 'Earlier version',
  ok: 'OK',
  failing: 'Failing',
  unknown: 'Unknown',
  not_configured: 'Not configured',
  partially_received: 'Part received',
  in_use: 'In use',
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
