import { Component, computed, inject, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { AffiliationGrant, InstitutionListItem, Page } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** Affiliation grants between colleges and universities (S5E-01): proposed here, approved by the college. */
@Component({
  selector: 'app-affiliations-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-page-header title="Affiliations" subtitle="Which colleges may send results to which university, for what, and until when." />
      <app-load-error [message]="grants.error()" (retry)="grants.reload()" />
      <div class="card list-card section">
        <ul class="list">
          @for (g of grants.value() ?? []; track g.id) {
            <li class="list-row">
              <span class="list-main">
                <span class="list-title">{{ g.college.name }} → {{ g.university.name }}</span>
                <span class="muted small">{{ g.purpose }} · {{ date(g.starts_on) }} to {{ date(g.ends_on) }} · {{ g.evidence }}</span>
              </span>
              <span class="badge" [class.badge-success]="g.in_effect">{{ g.status_label }}</span>
            </li>
          } @empty {
            <li class="list-row muted small">No affiliations yet.</li>
          }
        </ul>
      </div>
      <form id="propose" class="card stack section" (submit)="$event.preventDefault(); propose($any($event.target))">
        <h2 class="card-title">Propose an affiliation</h2>
        <p class="muted small">The college's Institution Admin approves it before anything can be sent.</p>
        <div class="grid">
          <div class="field">
            <label for="grant-college">College</label>
            <select id="grant-college">
              @for (i of colleges(); track i.id) { <option [value]="i.id">{{ i.display_name }}</option> }
            </select>
          </div>
          <div class="field">
            <label for="grant-university">University</label>
            <select id="grant-university">
              @for (i of universities(); track i.id) { <option [value]="i.id">{{ i.display_name }}</option> }
            </select>
            @if (errors()['university']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field"><label for="grant-starts">From</label><input id="grant-starts" type="date" /></div>
          <div class="field">
            <label for="grant-ends">Until</label><input id="grant-ends" type="date" />
            @if (errors()['ends_on']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field wide"><label for="grant-purpose">Purpose</label><input id="grant-purpose" placeholder="Central examination of results" /></div>
          <div class="field wide"><label for="grant-evidence">Approval evidence</label><input id="grant-evidence" placeholder="Affiliation order number" /></div>
        </div>
        <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Propose</button></div>
      </form>
    </div>
  `,
  styles: `
    .grid {
      display: grid;
      gap: 12px;

      @media (min-width: 900px) {
        grid-template-columns: repeat(4, minmax(0, 1fr));

        .wide {
          grid-column: span 2;
        }
      }
    }
  `,
})
export class AffiliationsPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly grants = load(() => this.api.get<AffiliationGrant[]>('platform/affiliations'));
  private readonly institutions = load(() => this.api.get<Page<InstitutionListItem>>('platform/institutions', { page_size: 200 }));
  protected readonly colleges = computed(() =>
    (this.institutions.value()?.results ?? []).filter((i) => i.category === 'college' || i.category === 'engineering_college'),
  );
  protected readonly universities = computed(() => (this.institutions.value()?.results ?? []).filter((i) => i.category === 'university'));
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  protected propose(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value.trim();
    const body = {
      college: field('grant-college'),
      university: field('grant-university'),
      purpose: field('grant-purpose'),
      starts_on: field('grant-starts'),
      ends_on: field('grant-ends'),
      evidence: field('grant-evidence'),
    };
    this.busy.set(true);
    this.errors.set({});
    this.api.post<AffiliationGrant>('platform/affiliations', body).subscribe({
      next: () => {
        this.busy.set(false);
        form.reset();
        this.toasts.show('Affiliation proposed; the college approves it.');
        this.grants.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.errors.set(fieldErrors(err));
        if (!Object.keys(fieldErrors(err)).length) {
          this.toasts.show(apiErrorMessage(err), 'danger');
        }
      },
    });
  }
}
