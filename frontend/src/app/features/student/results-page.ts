import { Component, inject } from '@angular/core';
import { Api } from '../../core/api/api';
import { IssuedDocumentT, ResultT } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PortalFrame } from '../apply/portal-frame';

/** A student's published results and the documents issued to them. */
@Component({
  selector: 'app-student-results-page',
  imports: [LoadError, PortalFrame],
  template: `
    <app-portal-frame heading="Results">
      <app-load-error [message]="results.error()" (retry)="results.reload()" />
      <section class="card stack">
        <h2 class="card-title">Published results</h2>
        <ul class="rows">
          @for (r of results.value() ?? []; track $index) {
            <li><span>{{ r.assessment }} <span class="muted small meta">{{ r.term }}</span></span>
              <span class="small">{{ r.total ?? r.outcome }}{{ r.grade ? ' · ' + r.grade : '' }}{{ r.revision > 1 ? ' · revised' : '' }}</span></li>
          } @empty {
            <li class="muted small">No results published yet.</li>
          }
        </ul>
      </section>
      <section class="card stack">
        <h2 class="card-title">Documents</h2>
        <ul class="rows">
          @for (d of documents.value() ?? []; track d.id) {
            <li><span>{{ d.title }} <span class="muted small meta">{{ d.number }} · {{ dateTime(d.issued_at) }}{{ d.status === 'superseded' ? ' · replaced by a newer one' : '' }}</span></span>
              <a class="small" [href]="'/verify/' + d.token" target="_blank" rel="noopener">Verification page</a></li>
          } @empty {
            <li class="muted small">Nothing issued yet.</li>
          }
        </ul>
      </section>
    </app-portal-frame>
  `,
  styles: `
  `,
})
export class StudentResultsPage {
  private readonly api = inject(Api);
  protected readonly dateTime = dateTime;
  protected readonly results = load(() => this.api.get<(ResultT & { assessment: string; term: string })[]>('student/results'));
  protected readonly documents = load(() => this.api.get<IssuedDocumentT[]>('student/documents'));
}
