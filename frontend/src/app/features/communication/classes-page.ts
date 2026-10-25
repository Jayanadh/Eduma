import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { ClassSessionT } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PortalFrame } from '../apply/portal-frame';

/** A student's online classes. */
@Component({
  selector: 'app-student-classes-page',
  imports: [LoadError, PortalFrame, RouterLink],
  template: `
    <app-portal-frame heading="Online classes">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      <ul class="bullets">
        @for (s of data.value() ?? []; track s.id) {
          <li><a [routerLink]="['/student/classes', s.id]">{{ s.title }}</a> <span class="muted small meta">{{ s.target.label }} · {{ dateTime(s.starts_at) }} · {{ s.state_label }}</span></li>
        } @empty {
          <li class="muted small">No online classes.</li>
        }
      </ul>
    </app-portal-frame>
  `,
  styles: `
    .bullets {
      padding-left: 18px;
    }
  `,
})
export class StudentClassesPage {
  private readonly api = inject(Api);
  protected readonly dateTime = dateTime;
  protected readonly data = load(() => this.api.get<ClassSessionT[]>('communication/classes'));
}
