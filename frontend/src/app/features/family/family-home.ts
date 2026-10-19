import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { FamilyChild } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PortalFrame } from '../apply/portal-frame';
import { ChildSummary } from './child-summary';

/** A guardian's children at this school: only those the school has linked to them, only what it shares. */
@Component({
  selector: 'app-family-home',
  imports: [ChildSummary, LoadError, PortalFrame, RouterLink],
  template: `
    <app-portal-frame heading="Your children">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as children) {
        @for (child of children; track child.id) {
          <a class="card child" [routerLink]="['/family/children', child.id]">
            <app-child-summary [child]="child" />
          </a>
        } @empty {
          <p class="notice notice-info">Nothing is shared here yet. The school links children to their guardians after checking who they are.</p>
        }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </app-portal-frame>
  `,
  styles: `
    .child {
      display: block;
      color: inherit;
      text-decoration: none;
    }
  `,
})
export class FamilyHome {
  private readonly api = inject(Api);
  protected readonly data = load(() => this.api.get<FamilyChild[]>('family/children'));
}
