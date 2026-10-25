import { Component, computed, inject, input, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AcademicYear, IssuedDocumentT, StudentRecord } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { ToastService } from '../../ui/toast';

/** Report cards, transcripts and awards on a student's record (S7-09..11): issue, see what was issued, revoke. */
@Component({
  selector: 'app-documents-section',
  template: `
    <section class="card stack">
      <h2 class="card-title">Documents</h2>
      <ul class="rows">
        @for (d of docs.value() ?? []; track d.id) {
          <li>
            <span><strong>{{ d.number }}</strong> {{ d.title }} <span class="muted small meta">{{ dateTime(d.issued_at) }} · {{ d.status }}{{ d.reason ? ': ' + d.reason : '' }}</span>
              <a class="small" [href]="'/verify/' + d.token" target="_blank" rel="noopener">verification page</a></span>
            @if (canIssue() && d.status === 'current') {
              <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Revoke ' + d.number" [disabled]="busy()" (click)="revoke(d)">Revoke</button>
            }
          </li>
        } @empty {
          <li class="muted small">Nothing issued yet.</li>
        }
      </ul>
      @if (canIssue()) {
        <form id="issue-document" class="row" (submit)="$event.preventDefault(); issue($any($event.target))">
          <div class="field"><label for="doc-kind">Issue</label>
            <select id="doc-kind" (change)="picked.set($any($event.target).value)">
              @if (reportCards()) { <option value="report_card">Report card</option> }
              <option value="transcript">Transcript</option>
              <option value="award">Award</option>
            </select></div>
          @if (kind() === 'report_card') {
            <div class="field"><label for="doc-term">Term</label>
              <select id="doc-term">@for (t of terms(); track t.id) { <option [value]="t.id">{{ t.label }}</option> }</select></div>
          }
          @if (kind() === 'award') {
            <div class="field grow"><label for="doc-exception">Authorised exception (only if credits fall short)</label><input id="doc-exception" /></div>
          }
          <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Issue</button>
        </form>
        @if (reportCards()) {
          <form id="promotion" class="row" (submit)="$event.preventDefault(); promote($any($event.target))">
            <div class="field"><label for="promo-year">Year</label>
              <select id="promo-year">@for (y of years.value() ?? []; track y.id) { <option [value]="y.id">{{ y.code }}</option> }</select></div>
            <div class="field"><label for="promo-decision">Decision</label>
              <select id="promo-decision"><option value="promote">Promote</option><option value="repeat">Repeat the year</option><option value="hold">Hold</option></select></div>
            <div class="field grow"><label for="promo-reason">Reason</label><input id="promo-reason" /></div>
            <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Record decision</button>
          </form>
        }
        @if (message(); as m) { <p class="field-error" role="alert">{{ m }}</p> }
      }
    </section>
  `,
  styles: `
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: end;
    }

    .grow {
      flex: 1 1 200px;
    }
  `,
})
export class DocumentsSection {
  readonly student = input.required<StudentRecord>();
  private readonly api = inject(Api);
  private readonly auth = inject(AuthStore);
  private readonly toasts = inject(ToastService);
  private readonly confirm = inject(ConfirmDialog);
  protected readonly dateTime = dateTime;
  protected readonly canIssue = computed(() => this.auth.can('results.publish'));
  protected readonly reportCards = computed(() => this.auth.user()?.membership?.modules_enabled?.includes('report_cards') ?? false);
  private readonly picked = signal('');
  /** What to issue: as chosen, else a report card where those are on, else a transcript. */
  protected readonly kind = computed(() => this.picked() || (this.reportCards() ? 'report_card' : 'transcript'));
  protected readonly docs = load(
    () => this.api.get<IssuedDocumentT[]>(`institution/results/students/${this.student().id}/documents`),
    () => this.student().id,
  );
  protected readonly years = load(() => this.api.get<AcademicYear[]>('institution/academics/years'));
  protected readonly terms = computed(() => (this.years.value() ?? []).flatMap((y) => y.terms.map((t) => ({ id: t.id, label: `${y.code} ${t.name}` }))));
  protected readonly busy = signal(false);
  protected readonly message = signal('');

  private run(request: ReturnType<Api['post']>, done: string): void {
    this.busy.set(true);
    this.message.set('');
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        this.docs.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.message.set(apiErrorMessage(err));
      },
    });
  }

  protected issue(form: HTMLFormElement): void {
    const kind = this.kind();
    const body: Record<string, string> = { kind };
    if (kind === 'report_card') {
      body['term'] = form.querySelector<HTMLSelectElement>('#doc-term')!.value;
    }
    if (kind === 'award') {
      body['exception'] = form.querySelector<HTMLInputElement>('#doc-exception')!.value.trim();
    }
    this.run(this.api.post(`institution/results/students/${this.student().id}/documents`, body), 'Issued.');
  }

  protected promote(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
    const body = { year: field('promo-year'), decision: field('promo-decision'), reason: field('promo-reason') };
    this.run(this.api.post(`institution/results/students/${this.student().id}/promotion`, body), 'Decision recorded.');
  }

  protected async revoke(d: IssuedDocumentT): Promise<void> {
    const reason = await this.confirm.prompt({ title: `Revoke ${d.number}?`, label: 'Why', confirmLabel: 'Revoke', required: true });
    if (reason) {
      this.run(this.api.post(`institution/results/documents/${d.id}/revoke`, { reason }), `${d.number} revoked.`);
    }
  }
}
