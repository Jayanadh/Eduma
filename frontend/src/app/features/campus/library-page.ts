import { Component, inject, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { LibraryLoan, LibraryTitle } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { SearchBox } from '../../ui/search-box';
import { ToastService } from '../../ui/toast';

/** The library desk (S10A-01..04): catalogue, issue by accession number, returns, renewals, reservations and fines. */
@Component({
  selector: 'app-library-page',
  imports: [PageHeader, SearchBox],
  template: `
    <div class="page">
      <app-page-header eyebrow="Campus" title="Library" subtitle="Issue and return by accession number. A returned book goes to the first person waiting." />
      <form id="issue" class="card row section" (submit)="$event.preventDefault(); issue($any($event.target))">
        <div class="field"><label for="issue-accession">Accession</label><input id="issue-accession" /></div>
        <div class="field"><label for="issue-student">Student number</label><input id="issue-student" placeholder="2026-0001" /></div>
        <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Issue</button>
      </form>
      <section class="card stack section">
        <h2 class="card-title">On loan</h2>
        <ul class="rows">
          @for (l of loans.value() ?? []; track l.id) {
            <li>
              <span><strong>{{ l.accession }}</strong> {{ l.title }} <span class="muted small">· {{ l.borrower }} · due {{ date(l.due_on) }}{{ l.renewals ? ' · renewed ' + l.renewals : '' }}</span></span>
              <span class="actions">
                <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Return ' + l.accession" (click)="act(l, 'return')">Return</button>
                <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Renew ' + l.accession" (click)="act(l, 'renew')">Renew</button>
                <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Mark ' + l.accession + ' lost'" (click)="act(l, 'lost')">Lost</button>
              </span>
            </li>
          } @empty {
            <li class="muted small">Nothing on loan.</li>
          }
        </ul>
      </section>
      <section class="card stack section">
        <h2 class="card-title">Catalogue</h2>
        <app-search-box id="title-search" label="Search titles" (search)="query.set($event)" />
        <ul class="rows">
          @for (t of titles.value() ?? []; track t.id) {
            <li><span><strong>{{ t.title }}</strong> <span class="muted small">{{ t.author }} · {{ t.available }} of {{ t.copies.length }} available{{ t.waiting ? ' · ' + t.waiting + ' waiting' : '' }}</span></span></li>
          }
        </ul>
        <form id="add-title" class="row" (submit)="$event.preventDefault(); add($any($event.target))">
          <div class="field grow"><label for="t-title">Title</label><input id="t-title" /></div>
          <div class="field"><label for="t-author">Author</label><input id="t-author" /></div>
          <div class="field"><label for="t-copies">Accession numbers (comma separated)</label><input id="t-copies" /></div>
          <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add title</button>
        </form>
      </section>
    </div>
  `,
  styles: `
    .row,
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: end;
    }

    .grow {
      flex: 1 1 200px;
    }

    .rows {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;

      li {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        gap: 8px;
      }
    }
  `,
})
export class LibraryPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly query = signal('');
  protected readonly titles = load(
    () => this.api.get<LibraryTitle[]>('institution/campus/titles', this.query() ? { search: this.query() } : {}),
    () => this.query(),
  );
  protected readonly loans = load(() => this.api.get<LibraryLoan[]>('institution/campus/loans', { active: 1 }));
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        this.loans.reload();
        this.titles.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected issue(form: HTMLFormElement): void {
    const accession = form.querySelector<HTMLInputElement>('#issue-accession')!.value.trim();
    const number = form.querySelector<HTMLInputElement>('#issue-student')!.value.trim();
    this.api.get<{ results: { id: string; number: string }[] }>('institution/students', { search: number }).subscribe({
      next: (found) => {
        const student = found.results.find((s) => s.number === number);
        if (!student) {
          this.toasts.show(`No student ${number}.`, 'danger');
          return;
        }
        this.run(this.api.post('institution/campus/loans', { accession, student: student.id }), `${accession} issued.`, () => form.reset());
      },
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }

  protected act(loan: LibraryLoan, action: 'return' | 'renew' | 'lost'): void {
    const words = { return: 'Returned.', renew: 'Renewed.', lost: 'Marked lost; the replacement cost is charged.' };
    this.run(this.api.post(`institution/campus/loans/${loan.id}/${action}`, {}), words[action]);
  }

  protected add(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!.value.trim();
    const body = { title: field('t-title'), author: field('t-author'), copies: field('t-copies').split(',').map((c) => c.trim()).filter(Boolean) };
    this.run(this.api.post('institution/campus/titles', body), 'Title added.', () => form.reset());
  }
}
