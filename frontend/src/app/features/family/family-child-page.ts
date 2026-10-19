import { Component, inject, input } from '@angular/core';
import { Api } from '../../core/api/api';
import { FamilyChild } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PortalFrame } from '../apply/portal-frame';
import { ChildSummary } from './child-summary';

/** One child, as their guardian may see them. Attendance, results and fees join this page module by module. */
@Component({
  selector: 'app-family-child-page',
  imports: [ChildSummary, LoadError, PortalFrame],
  template: `
    <app-portal-frame [heading]="data.value()?.full_name ?? 'Your child'">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as child) {
        <section class="card"><app-child-summary [child]="child" /></section>
        @if (child.shared) {
          <p class="notice notice-info">More arrives here with each module your school switches on.</p>
        }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </app-portal-frame>
  `,
})
export class FamilyChildPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  protected readonly data = load(
    () => this.api.get<FamilyChild>(`family/children/${this.id()}`),
    () => this.id(),
  );
}
