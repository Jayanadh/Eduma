import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AcademicYear, AffiliationGrant, Program, SubmissionBatch } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** An institution's affiliations (SCR-031): a college approves grants and sends result batches; a university reviews
 * what its colleges sent. */
@Component({
  selector: 'app-institution-affiliations-page',
  imports: [LoadError, PageHeader, RouterLink],
  template: `
    <div class="page">
      <app-page-header eyebrow="Academics" title="Affiliations" subtitle="Results cross to another institution only under a grant in effect." />
      <app-load-error [message]="grants.error()" (retry)="grants.reload()" />
      @for (g of grants.value() ?? []; track g.id) {
        <section class="card stack section">
          <h2 class="card-title">{{ g.college.name }} → {{ g.university.name }}</h2>
          <p class="small">{{ g.purpose }} <span class="muted">· {{ date(g.starts_on) }} to {{ date(g.ends_on) }} · {{ g.evidence }} · shares {{ g.categories.join(', ') }}</span></p>
          <p class="small"><span class="badge" [class.badge-success]="g.in_effect">{{ g.in_effect ? 'In effect' : g.status_label }}</span>{{ g.revoked_reason ? ' ' + g.revoked_reason : '' }}</p>
          <div class="actions">
            @if (g.status === 'proposed' && g.side === 'college') {
              <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="approve(g)">Approve</button>
            }
            @if (g.status !== 'revoked') {
              <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="revoke(g)">Revoke</button>
            }
          </div>
          @if (g.side === 'college' && g.in_effect && canSubmit()) {
            <form class="row" [id]="'build-' + g.id" (submit)="$event.preventDefault(); build(g, $any($event.target))">
              <div class="field">
                <label [for]="'batch-program-' + g.id">Program</label>
                <select [id]="'batch-program-' + g.id">
                  @for (p of programs.value() ?? []; track p.id) { <option [value]="p.id">{{ p.code }} · {{ p.name }}</option> }
                </select>
              </div>
              <div class="field">
                <label [for]="'batch-term-' + g.id">Term</label>
                <select [id]="'batch-term-' + g.id">
                  @for (t of terms(); track t.id) { <option [value]="t.id">{{ t.label }}</option> }
                </select>
              </div>
              <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Build a batch</button>
            </form>
          }
        </section>
      } @empty {
        <p class="muted section">No affiliations. Eduma sets one up when a college and a university agree.</p>
      }
      @if (sent.value()?.length) {
        <section class="card list-card section">
          <h2 class="card-title">Batches sent</h2>
          <ul class="list">
            @for (b of sent.value() ?? []; track b.id) {
              <li><a class="list-row" [routerLink]="['/app/affiliations/batches', b.id]"><span class="list-main"><span class="list-title">{{ b.program }} · {{ b.term }} · revision {{ b.revision }}</span><span class="muted small">to {{ b.university }} · {{ b.status_label }}</span></span></a></li>
            }
          </ul>
        </section>
      }
      @if (received.value()?.length) {
        <section class="card list-card section">
          <h2 class="card-title">Batches received</h2>
          <ul class="list">
            @for (b of received.value() ?? []; track b.id) {
              <li><a class="list-row" [routerLink]="['/app/affiliations/received', b.id]"><span class="list-main"><span class="list-title">{{ b.college }} · {{ b.program }} · {{ b.term }} · revision {{ b.revision }}</span><span class="muted small">{{ b.rows.length }} students · {{ b.status_label }}</span></span></a></li>
            }
          </ul>
        </section>
      }
    </div>
  `,
  styles: `
    .actions,
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: end;
    }
  `,
})
export class InstitutionAffiliationsPage {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  private readonly confirm = inject(ConfirmDialog);
  private readonly auth = inject(AuthStore);
  protected readonly date = date;
  protected readonly canSubmit = computed(() => this.auth.can('affiliation.submit'));
  protected readonly grants = load(() => this.api.get<AffiliationGrant[]>('institution/affiliations'));
  protected readonly programs = load(() =>
    this.auth.can('affiliation.submit') ? this.api.get<Program[]>('institution/academics/programs') : of([] as Program[]),
  );
  private readonly years = load(() => this.api.get<AcademicYear[]>('institution/academics/years'));
  protected readonly terms = computed(() =>
    (this.years.value() ?? []).flatMap((y) => y.terms.map((t) => ({ id: t.id, label: `${y.code} ${t.name}` }))),
  );
  protected readonly sent = load(() =>
    this.auth.can('affiliation.submit') ? this.api.get<SubmissionBatch[]>('institution/affiliations/sent') : of([] as SubmissionBatch[]),
  );
  protected readonly received = load(() =>
    this.auth.can('affiliation.review') ? this.api.get<SubmissionBatch[]>('institution/affiliations/received') : of([] as SubmissionBatch[]),
  );
  protected readonly busy = signal(false);

  protected approve(g: AffiliationGrant): void {
    this.post(`institution/affiliations/${g.id}/approve`, { version: g.version }, 'Affiliation approved.');
  }

  protected async revoke(g: AffiliationGrant): Promise<void> {
    const reason = await this.confirm.prompt({
      title: `Revoke the affiliation with ${g.university.name}?`,
      message: 'Nothing more can be sent or read under it.',
      label: 'Reason',
      confirmLabel: 'Revoke',
    });
    if (reason) {
      this.post(`institution/affiliations/${g.id}/revoke`, { version: g.version, reason }, 'Affiliation revoked.');
    }
  }

  protected build(g: AffiliationGrant, form: HTMLFormElement): void {
    const body = {
      program: form.querySelector<HTMLSelectElement>(`#batch-program-${g.id}`)!.value,
      term: form.querySelector<HTMLSelectElement>(`#batch-term-${g.id}`)!.value,
    };
    this.busy.set(true);
    this.api.post<SubmissionBatch>(`institution/affiliations/${g.id}/batches`, body).subscribe({
      next: (made) => {
        this.busy.set(false);
        this.router.navigate(['/app/affiliations/batches', made.id]);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  private post(path: string, body: object, message: string): void {
    this.busy.set(true);
    this.api.post(path, body).subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(message);
        this.grants.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
