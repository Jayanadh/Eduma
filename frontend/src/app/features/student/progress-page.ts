import { Component, inject } from '@angular/core';
import { Api } from '../../core/api/api';
import { DegreeProgress } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PortalFrame } from '../apply/portal-frame';
import { DegreeProgressView } from '../academics/degree-progress';

/** A student's own advisory degree progress (SCR-029). */
@Component({
  selector: 'app-progress-page',
  imports: [DegreeProgressView, LoadError, PortalFrame],
  template: `
    <app-portal-frame heading="Degree progress">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as p) {
        <section class="card"><app-degree-progress [progress]="p" /></section>
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </app-portal-frame>
  `,
})
export class ProgressPage {
  private readonly api = inject(Api);
  protected readonly data = load(() => this.api.get<DegreeProgress>('student/progress'));
}
