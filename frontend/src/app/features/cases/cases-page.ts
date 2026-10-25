import { NgTemplateOutlet } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { SearchBox } from '../../ui/search-box';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from '../apply/portal-frame';
import { CASE_TYPES, CaseT } from './case-types';

/**
 * Service requests and grievances (S10C-01..04). Anyone opens one; each person sees only what they may: their own,
 * the ones assigned to them, and for triage the queue (confidential cases as a shell only).
 */
@Component({
  selector: 'app-cases-page',
  imports: [LoadError, NgTemplateOutlet, PageHeader, PortalFrame, RouterLink, SearchBox],
  template: `
    <ng-template #body>
      <p class="muted small">Cases are read during working hours. If someone is in danger now, call the emergency number or your institution's urgent contact.</p>
      @if (portal()) {
      <form id="open-case" class="card stack section" (submit)="$event.preventDefault(); open($any($event.target))">
        <h2 class="card-title">Raise a case</h2>
        <div class="field"><label for="case-type">Kind</label>
          <select id="case-type">@for (t of types; track t[0]) { <option [value]="t[0]">{{ t[1] }}</option> }</select></div>
        <div class="field"><label for="case-subject">Subject</label><input id="case-subject" maxlength="150" required /></div>
        <div class="field"><label for="case-description">What happened, and what would help</label><textarea id="case-description" rows="4" maxlength="4000" required></textarea></div>
        <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Send</button></div>
      </form>
      <section class="card stack section">
        <app-search-box id="case-search" label="Search cases" (search)="query.set($event)" />
        <app-load-error [message]="list.error()" (retry)="list.reload()" />
        <ul class="rows">
          @for (c of list.value() ?? []; track c.id) {
            <li>
              <a [routerLink]="[base(), c.id]"><strong>{{ c.number }}</strong> {{ c.subject ?? c.type_label }}</a>
              <span class="muted small">{{ c.type_label }} · {{ c.state_label }}{{ c.assignee ? ' · ' + c.assignee : '' }}{{ c.due_at ? ' · due ' + dateTime(c.due_at) : '' }}@if (c.overdue) { · <strong>overdue</strong> }</span>
            </li>
          } @empty {
            <li class="muted small">No cases.</li>
          }
        </ul>
      </section>
      } @else {
      <section class="card stack section">
        <app-search-box id="case-search" label="Search cases" (search)="query.set($event)" />
        <app-load-error [message]="list.error()" (retry)="list.reload()" />
        <ul class="rows">
          @for (c of list.value() ?? []; track c.id) {
            <li>
              <a [routerLink]="[base(), c.id]"><strong>{{ c.number }}</strong> {{ c.subject ?? c.type_label }}</a>
              <span class="muted small">{{ c.type_label }} · {{ c.state_label }}{{ c.assignee ? ' · ' + c.assignee : '' }}{{ c.due_at ? ' · due ' + dateTime(c.due_at) : '' }}@if (c.overdue) { · <strong>overdue</strong> }</span>
            </li>
          } @empty {
            <li class="muted small">No cases.</li>
          }
        </ul>
      </section>
      <form id="open-case" class="card stack section" (submit)="$event.preventDefault(); open($any($event.target))">
        <h2 class="card-title">Raise a case</h2>
        <div class="field"><label for="case-type">Kind</label>
          <select id="case-type">@for (t of types; track t[0]) { <option [value]="t[0]">{{ t[1] }}</option> }</select></div>
        <div class="field"><label for="case-subject">Subject</label><input id="case-subject" maxlength="150" required /></div>
        <div class="field"><label for="case-description">What happened, and what would help</label><textarea id="case-description" rows="4" maxlength="4000" required></textarea></div>
        <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Send</button></div>
      </form>
      }
    </ng-template>
    @if (portal()) {
      <app-portal-frame heading="Cases"><ng-container [ngTemplateOutlet]="body" /></app-portal-frame>
    } @else {
      <div class="page">
        <app-page-header eyebrow="People" title="Cases" subtitle="Service requests and grievances. Confidential cases are seen only by the person handling them." />
        <ng-container [ngTemplateOutlet]="body" />
      </div>
    }
  `,
  styles: `
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
export class CasesPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly router = inject(Router);
  protected readonly dateTime = dateTime;
  protected readonly types = CASE_TYPES;
  protected readonly portal = signal(!!inject(ActivatedRoute).snapshot.data['portal']);
  protected readonly base = computed(() => (this.portal() ? '/cases' : '/app/cases'));
  protected readonly query = signal('');
  protected readonly list = load(
    () => this.api.get<CaseT[]>('service-cases/', this.query() ? { search: this.query() } : {}),
    () => this.query(),
  );
  protected readonly busy = signal(false);

  protected open(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(`#${id}`)!.value.trim();
    const body = { case_type: field('case-type'), subject: field('case-subject'), description: field('case-description') };
    this.busy.set(true);
    this.api.post<CaseT>('service-cases/', body).subscribe({
      next: (made) => {
        this.busy.set(false);
        this.toasts.show(`${made.number} sent.`);
        this.router.navigate([this.base(), made.id]);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
