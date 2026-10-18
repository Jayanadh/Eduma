import { Component, computed, DestroyRef, effect, inject, input, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { ModuleInfo, SettingDetail, SettingRevisionItem } from '../../core/api/types';
import { date, dateTime } from '../../core/format';
import { load } from '../../core/load';
import { UnsavedChanges } from '../../core/unsaved-changes';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { StatusBadge } from '../../ui/status-badge';
import { ToastService } from '../../ui/toast';
import { ModulePicker } from '../console/module-picker';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
  'November', 'December'];

/** The institution's own calendar day for a date input: today in India time, as YYYY-MM-DD. */
function today(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date());
}

/**
 * One setting: what is in force, a draft with a preview of what it would change, publishing or sending it for
 * approval from a chosen day, deciding on someone else's waiting change, and the history with restore.
 */
@Component({
  selector: 'app-setting-editor-page',
  imports: [LoadError, ModulePicker, PageHeader, Pager, StatusBadge],
  template: `
    <div class="page">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as s) {
        <app-page-header eyebrow="Settings" [title]="s.label" backLink="/app/settings" />
        <section class="card stack section">
          <p class="muted small">{{ s.help }}</p>
          <p><strong>Now:</strong> {{ s.description_now }}</p>
          @if (s.scheduled; as next) {
            <p class="small">From {{ date(next.effective_from) }}: {{ next.description }}</p>
          }
        </section>

        @if (s.pending; as p) {
          <section class="card card-strong stack section">
            <h2 class="card-title">Waiting for approval</h2>
            <p>{{ p.description }}, from {{ date(p.effective_from) }}.</p>
            <p class="muted small">Sent by {{ p.submitted_by_name }} on {{ dateTime(p.submitted_at) }}. Why: {{ p.reason }}</p>
            <div class="form-actions">
              @if (p.can_approve) {
                <button type="button" class="btn btn-primary" [disabled]="busy()" (click)="approve(p)">Approve</button>
                <button type="button" class="btn btn-secondary" [disabled]="busy()" (click)="giveBack(p)">Return with a note</button>
              }
              @if (p.mine) {
                <button type="button" class="btn btn-secondary" [disabled]="busy()" (click)="withdraw(p)">Withdraw</button>
              }
            </div>
          </section>
        } @else if (s.draft; as d) {
          <section class="card card-strong stack section">
            <h2 class="card-title">Your change</h2>
            @if (d.return_note) {
              <p class="notice notice-warning" role="status">Returned: {{ d.return_note }}</p>
            }
            @switch (s.kind) {
              @case ('month') {
                <div class="field">
                  <label for="setting-month">Month</label>
                  <select id="setting-month" (change)="choose(+$any($event.target).value)">
                    @for (name of months; track $index) {
                      <option [value]="$index + 1" [selected]="value() === $index + 1">{{ name }}</option>
                    }
                  </select>
                </div>
              }
              @case ('bool') {
                <label class="check"><input id="setting-on" type="checkbox" [checked]="value() === true" (change)="choose($any($event.target).checked)" /> On</label>
              }
              @case ('modules') {
                <app-module-picker [catalogue]="catalogue()" [selected]="modulesValue()" (selectedChange)="choose($event)" />
              }
            }
            @if (errors()['value']; as message) { <p class="field-error">{{ message }}</p> }
            <div class="form-actions">
              <button type="button" class="btn btn-secondary" [disabled]="busy() || !changed()" (click)="saveDraft(d)">Save draft</button>
            </div>
            @if (s.preview.length) {
              <div class="notice notice-info" role="status">
                @for (line of s.preview; track $index) { <p>{{ line }}</p> }
              </div>
            }
            <div class="form-grid">
              <div class="field">
                <label for="setting-starts">Starts on</label>
                <input id="setting-starts" type="date" [min]="today" [value]="starts()" (input)="starts.set($any($event.target).value)" />
                @if (errors()['effective_from']; as message) { <span class="field-error">{{ message }}</span> }
              </div>
              <div class="field full">
                <label for="setting-why">Why</label>
                <textarea id="setting-why" rows="2" (input)="why.set($any($event.target).value)">{{ why() }}</textarea>
                @if (errors()['reason']; as message) { <span class="field-error">{{ message }}</span> }
              </div>
            </div>
            @if (error()) {
              <p class="field-error" role="alert">{{ error() }}</p>
            }
            <div class="form-actions">
              <button type="button" class="btn btn-primary" [disabled]="busy() || changed()" (click)="submit(d)">
                {{ s.needs_approval ? 'Send for approval' : 'Publish' }}
              </button>
              <button type="button" class="btn btn-secondary" [disabled]="busy()" (click)="withdraw(d)">Discard draft</button>
            </div>
            @if (changed()) {
              <p class="muted small">Save the draft first to see what it changes.</p>
            }
          </section>
        } @else {
          <button type="button" class="btn btn-primary section" [disabled]="busy()" (click)="start()">Start a change</button>
        }

        <section class="section stack">
          <h2 class="card-title">History</h2>
          @if (s.history.results.length) {
            <div class="card list-card">
              <ul class="list">
                @for (r of s.history.results; track r.id) {
                  <li class="list-row">
                    <span class="list-main">
                      <span class="list-title">{{ r.description }}</span>
                      <span class="muted small">
                        @if (r.effective_from) { From {{ date(r.effective_from) }} · }
                        {{ r.approved_by_name ? 'approved by ' + r.approved_by_name : (r.submitted_by_name ?? r.created_by_name) }}
                        @if (r.reason) { · {{ r.reason }} }
                      </span>
                    </span>
                    <app-status-badge [status]="r.status === 'published' ? 'active' : 'archived'" [label]="statusLabel(r)" />
                    <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy() || !!s.pending" (click)="restore(s, r)">Restore</button>
                  </li>
                }
              </ul>
            </div>
            <app-pager [page]="historyPage()" [count]="s.history.count" (go)="historyPage.set($event)" />
          } @else {
            <p class="muted">No earlier versions.</p>
          }
        </section>
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
})
export class SettingEditorPage {
  readonly key = input.required<string>();
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  private readonly unsaved = inject(UnsavedChanges);
  protected readonly date = date;
  protected readonly dateTime = dateTime;
  protected readonly months = MONTHS;
  protected readonly today = today();

  protected readonly historyPage = signal(1);
  protected readonly data = load(
    () => this.api.get<SettingDetail>(`institution/settings/${this.key()}`, { page: this.historyPage() }),
    () => [this.key(), this.historyPage()],
  );
  /** The value being edited, before it is saved into the draft. */
  protected readonly value = signal<unknown>(null);
  protected readonly starts = signal(today());
  protected readonly why = signal('');
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');

  protected readonly changed = computed(() => {
    const draft = this.data.value()?.draft;
    return !!draft && JSON.stringify(this.value()) !== JSON.stringify(draft.value);
  });
  protected readonly modulesValue = computed(() => (this.value() as string[] | null) ?? []);
  protected readonly catalogue = computed<ModuleInfo[]>(() =>
    (this.data.value()?.choices ?? []).map((choice) => ({ ...choice, default_for: [], available: false })),
  );

  constructor() {
    effect(() => {
      const draft = this.data.value()?.draft;
      this.value.set(draft ? draft.value : null);
    });
    effect(() => this.unsaved.dirty.set(this.changed()));
    inject(DestroyRef).onDestroy(() => this.unsaved.dirty.set(false));
  }

  protected choose(value: unknown): void {
    this.value.set(value);
  }

  protected statusLabel(revision: SettingRevisionItem): string {
    return { published: 'Published', superseded: 'Replaced before it started', withdrawn: 'Withdrawn' }[
      revision.status as 'published' | 'superseded' | 'withdrawn'
    ];
  }

  /** Every change answers with the whole setting. */
  private send(path: string, body: unknown, method: 'post' | 'put', done: string): void {
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    const request =
      method === 'put'
        ? this.api.put<SettingDetail>(`institution/settings/${this.key()}${path}`, body)
        : this.api.post<SettingDetail>(`institution/settings/${this.key()}${path}`, body);
    request.subscribe({
      next: (detail) => {
        this.busy.set(false);
        this.data.value.set(detail);
        if (done) {
          this.toasts.show(done);
        }
      },
      error: (err) => {
        this.busy.set(false);
        const fields = fieldErrors(err);
        this.errors.set(fields);
        if (!Object.keys(fields).length) {
          this.error.set(apiErrorMessage(err));
          this.toasts.show(apiErrorMessage(err), 'danger');
        }
      },
    });
  }

  protected start(): void {
    this.send('/draft', {}, 'post', '');
  }

  protected saveDraft(draft: SettingRevisionItem): void {
    this.send('/draft', { version: draft.version, value: this.value() }, 'put', '');
  }

  protected submit(draft: SettingRevisionItem): void {
    const done = this.data.value()?.needs_approval ? 'Sent for approval.' : 'Published.';
    this.send('/draft/submit', { version: draft.version, effective_from: this.starts(), reason: this.why() }, 'post', done);
  }

  protected withdraw(revision: SettingRevisionItem): void {
    this.send('/draft/withdraw', { version: revision.version }, 'post', 'Withdrawn.');
  }

  protected approve(revision: SettingRevisionItem): void {
    this.send(`/revisions/${revision.id}/approve`, { version: revision.version }, 'post', 'Approved and published.');
  }

  protected async giveBack(revision: SettingRevisionItem): Promise<void> {
    const note = await this.confirm.prompt({
      title: 'Return this change?',
      message: 'It goes back to a draft with your note, for the person who sent it.',
      label: 'What needs to change',
      type: 'textarea',
      required: true,
      confirmLabel: 'Return',
    });
    if (note !== null) {
      this.send(`/revisions/${revision.id}/return`, { version: revision.version, note }, 'post', 'Returned.');
    }
  }

  protected restore(detail: SettingDetail, revision: SettingRevisionItem): void {
    this.send(`/revisions/${revision.id}/restore`, { version: detail.draft?.version ?? null }, 'post', 'Restored into a draft.');
  }
}
