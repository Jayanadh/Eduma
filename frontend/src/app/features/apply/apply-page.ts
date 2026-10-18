import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { PublicAdmissions } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { SiteStore } from '../../core/site-store';
import { Icon } from '../../ui/icon';
import { LoadError } from '../../ui/load-error';

/** The institution's admissions, for anyone: open cycles, their places and what to have ready, and how to start. */
@Component({
  selector: 'app-apply-page',
  imports: [Icon, LoadError, RouterLink],
  template: `
    <main class="stage">
      <div class="apply">
        <a class="back" routerLink="/"><app-icon name="chevron-left" [size]="16" /> {{ site.institutionName() }}</a>
        <h1>Admissions</h1>
        <app-load-error [message]="data.error()" (retry)="data.reload()" />
        @if (data.value(); as admissions) {
          @if (admissions.cycles.length) {
            @for (cycle of admissions.cycles; track cycle.id) {
              <section class="card stack">
                <h2 class="card-title">{{ cycle.name }}</h2>
                <p class="muted small">For the {{ cycle.academic_year }} academic year · open {{ date(cycle.opens_on) }} to {{ date(cycle.closes_on) }}</p>
                @if (cycle.instructions) { <p>{{ cycle.instructions }}</p> }
                <h3 class="small">Places</h3>
                <ul class="chips">
                  @for (place of cycle.places; track place.id) {
                    <li class="chip">{{ place.label }}{{ place.campus_name ? ' · ' + place.campus_name : '' }}</li>
                  }
                </ul>
                @if (cycle.documents.length) {
                  <h3 class="small">Have these ready</h3>
                  <ul class="docs">
                    @for (doc of cycle.documents; track doc.code) {
                      <li>{{ doc.label }}{{ doc.required ? '' : ' (if you have it)' }}</li>
                    }
                  </ul>
                }
              </section>
            }
            <div class="actions">
              @if (auth.user()?.membership?.kind === 'applicant') {
                <a class="btn btn-primary" routerLink="/apply/applications">Go to your applications</a>
              } @else {
                <a class="btn btn-primary" routerLink="/apply/signup">Start an application</a>
                <a class="btn btn-secondary" routerLink="/login">I already have an account</a>
              }
            </div>
          } @else {
            <p class="notice notice-info">Admissions are not open right now. Please check back later.</p>
          }
        } @else if (data.loading()) {
          <p class="muted" role="status">Loading…</p>
        }
      </div>
    </main>
  `,
  styles: `
    .stage {
      min-height: 100vh;
      padding: 32px 16px;
      background: var(--surface-2);
    }

    .apply {
      display: flex;
      flex-direction: column;
      gap: 16px;
      max-width: 760px;
      margin: 0 auto;
    }

    .back {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      color: inherit;
      font-weight: 700;
    }

    .docs {
      margin: 0;
      padding-left: 20px;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
  `,
})
export class ApplyPage {
  private readonly api = inject(Api);
  protected readonly auth = inject(AuthStore);
  protected readonly site = inject(SiteStore);
  protected readonly date = date;
  protected readonly data = load(() => this.api.get<PublicAdmissions>('public/admissions'));
}
