import { Component, inject, input, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { HistoryEntry, Page } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { Pager } from '../../ui/pager';

/** What has happened to this student's record, newest first. */
@Component({
  selector: 'app-history-section',
  imports: [LoadError, Pager],
  template: `
    <section class="card stack">
      <h2 class="card-title">History</h2>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as result) {
        <ul class="plain">
          @for (entry of result.results; track $index) {
            <li>
              <span>{{ entry.summary }}</span>
              <span class="muted small">{{ dateTime(entry.at) }}{{ entry.actor ? ' · ' + entry.actor : '' }}</span>
            </li>
          } @empty {
            <li class="muted small">Nothing recorded yet.</li>
          }
        </ul>
        <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
      }
    </section>
  `,
  styles: `
    .plain {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;

      li {
        display: flex;
        flex-direction: column;
      }
    }
  `,
})
export class HistorySection {
  readonly studentId = input.required<string>();
  private readonly api = inject(Api);
  protected readonly dateTime = dateTime;
  protected readonly page = signal(1);
  protected readonly data = load(
    () =>
      this.api.get<Page<HistoryEntry>>(`institution/students/${this.studentId()}/history`, { page: this.page() }),
    () => [this.studentId(), this.page()],
  );
}
