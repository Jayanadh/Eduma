import { Component, inject, input } from '@angular/core';
import { Api } from '../../core/api/api';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';

/** The students registered in an offering the teacher teaches: number, name and status only. */
@Component({
  selector: 'app-teaching-offering-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="My classes" title="Class list" backLink="/app/teaching" />
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      <div class="card list-card section">
        <ul class="list">
          @for (s of data.value() ?? []; track s.number) {
            <li class="list-row"><span class="list-main"><span class="list-title">{{ s.number }} · {{ s.full_name }}</span></span></li>
          } @empty {
            <li class="list-row muted small">Nobody is registered yet.</li>
          }
        </ul>
      </div>
    </div>
  `,
})
export class TeachingOfferingPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  protected readonly data = load(
    () => this.api.get<{ number: string; full_name: string; status: string }[]>(`teaching/offerings/${this.id()}/students`),
    () => this.id(),
  );
}
