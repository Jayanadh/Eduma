import { Component, inject, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { StatusBadge } from '../../ui/status-badge';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { CycleT, EvidenceT, ROW_STYLES } from './types';

/** Quality evidence (S10C-09): request evidence by criterion, accept or return each version, freeze and export. */
@Component({
  selector: 'app-quality-page',
  imports: [PageHeader, StatusBadge],
  template: `
    <div class="page">
      <app-page-header eyebrow="Academics" title="Quality evidence" subtitle="A frozen cycle is a record of what was assembled, not an accreditation decision." />
      <section class="card stack section">
        <h2 class="card-title">Review cycles</h2>
        <ul class="rows">
          @for (c of cycles.value() ?? []; track c.id) {
            <li>
              <span><strong>{{ c.framework }}</strong> {{ c.period }} <span class="muted small">{{ c.frozen_at ? '· frozen ' + dateTime(c.frozen_at) : '· open' }}</span></span>
              <span class="actions">
                <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Open ' + c.framework + ' ' + c.period" (click)="open.set(c.id)">Open</button>
                @if (c.frozen_at) { <a class="btn btn-secondary btn-sm" [href]="'/api/v1/development/cycles/' + c.id + '/export'" download>Export</a> }
              </span>
            </li>
          }
        </ul>
        <form id="add-cycle" class="row" (submit)="$event.preventDefault(); addCycle($any($event.target))">
          <div class="field"><label for="cycle-framework">Framework</label><input id="cycle-framework" maxlength="60" placeholder="NAAC" required /></div>
          <div class="field"><label for="cycle-period">Period</label><input id="cycle-period" maxlength="30" placeholder="2025-26" required /></div>
          <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Start a cycle</button>
        </form>
      </section>
      @if (cycle.value(); as c) {
        <section class="card stack section">
          <h2 class="card-title">{{ c.framework }} {{ c.period }}</h2>
          <ul class="rows">
            @for (r of c.requests ?? []; track r.id) {
              <li>
                <span><strong>{{ r.criterion }}</strong> {{ r.title }} <app-status-badge [status]="r.state" /><span class="muted small meta">{{ r.owner }} · {{ r.versions.length }} version{{ r.versions.length === 1 ? '' : 's' }}{{ r.note ? ' · ' + r.note : '' }}</span></span>
                <span class="actions">
                  @for (v of r.versions; track v.id) { <a class="small" [href]="'/api/v1/development/evidence-files/' + v.id">v{{ v.number }}</a> }
                  @if (r.state === 'submitted' && !c.frozen_at) {
                    <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Accept ' + r.criterion" (click)="review(r, 'accept')">Accept</button>
                    <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Return ' + r.criterion" (click)="review(r, 'return')">Return</button>
                  }
                </span>
              </li>
            } @empty {
              <li class="muted small">Nothing requested yet.</li>
            }
          </ul>
          @if (!c.frozen_at) {
            <form id="add-request" class="row" (submit)="$event.preventDefault(); request(c, $any($event.target))">
              <div class="field"><label for="req-criterion">Criterion</label><input id="req-criterion" maxlength="20" placeholder="3.2.1" required /></div>
              <div class="field grow"><label for="req-title">Evidence</label><input id="req-title" maxlength="200" required /></div>
              <div class="field"><label for="req-owner">Owner's username</label><input id="req-owner" required /></div>
              <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Request</button>
            </form>
            <div><button type="button" id="freeze" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="freeze(c)">Freeze the cycle</button></div>
          } @else {
            <p class="muted small">Snapshot SHA-256 {{ c.snapshot_hash }}</p>
          }
        </section>
      }
    </div>
  `,
  styles: [ROW_STYLES],
})
export class QualityPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly dialog = inject(ConfirmDialog);
  protected readonly dateTime = dateTime;
  protected readonly open = signal('');
  protected readonly cycles = load(() => this.api.get<CycleT[]>('development/cycles'));
  protected readonly cycle = load(
    () => (this.open() ? this.api.get<CycleT>(`development/cycles/${this.open()}`) : of(null)),
    () => this.open(),
  );
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        this.cycles.reload();
        this.cycle.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected addCycle(form: HTMLFormElement): void {
    const f = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!.value.trim();
    this.api.post<CycleT>('development/cycles', { framework: f('cycle-framework'), period: f('cycle-period') }).subscribe({
      next: (made) => {
        form.reset();
        this.cycles.reload();
        this.open.set(made.id);
      },
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }

  protected request(c: CycleT, form: HTMLFormElement): void {
    const f = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!.value.trim();
    const body = { criterion: f('req-criterion'), title: f('req-title'), username: f('req-owner') };
    this.run(this.api.post(`development/cycles/${c.id}/requests`, body), 'Requested.', () => form.reset());
  }

  protected async review(r: EvidenceT, action: 'accept' | 'return'): Promise<void> {
    const note = action === 'return' ? await this.dialog.prompt({ title: `Return ${r.criterion}`, label: 'What is missing', confirmLabel: 'Return', required: true }) : '';
    if (note !== null) {
      this.run(this.api.post(`development/evidence/${r.id}/${action}`, { note }), action === 'accept' ? 'Accepted.' : 'Returned to the owner.');
    }
  }

  protected async freeze(c: CycleT): Promise<void> {
    const sure = await this.dialog.ask({ title: `Freeze ${c.framework} ${c.period}?`, message: 'Nothing in it can change afterwards.', confirmLabel: 'Freeze', tone: 'danger' });
    if (sure) {
      this.run(this.api.post(`development/cycles/${c.id}/freeze`, {}), 'Frozen.');
    }
  }
}
