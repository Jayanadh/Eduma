import { Component, inject } from '@angular/core';
import { Api } from '../../core/api/api';
import { FeeStatement } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PortalFrame } from '../apply/portal-frame';
import { PayOnline } from '../fees/pay-online';

/** A student's own fee statement. */
@Component({
  selector: 'app-student-fees-page',
  imports: [LoadError, PayOnline, PortalFrame],
  template: `
    <app-portal-frame heading="Fees">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as s) {
        <section class="card"><app-pay-online [statement]="s" orders="student/fees/orders" (ordered)="data.reload()" /></section>
      }
    </app-portal-frame>
  `,
})
export class StudentFeesPage {
  private readonly api = inject(Api);
  protected readonly data = load(() => this.api.get<FeeStatement>('student/fees'));
}
