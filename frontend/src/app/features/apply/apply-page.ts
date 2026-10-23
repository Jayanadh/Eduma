import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
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
  imports: [Icon, LoadError, ReactiveFormsModule, RouterLink],
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
              @if (auth.user()?.membership?.kind === 'applicant' || auth.user()?.membership?.kind === 'guardian') {
                <a class="btn btn-primary" routerLink="/apply/applications">Go to your applications</a>
              } @else {
                <a class="btn btn-primary" routerLink="/apply/signup">Start an application</a>
                <a class="btn btn-secondary" routerLink="/login">I already have an account</a>
              }
            </div>
            <section class="card stack">
              <h2 class="card-title">Ask a question</h2>
              @if (reference()) {
                <p class="notice notice-success" role="status">Thank you. The school will reply; your reference is <strong>{{ reference() }}</strong>.</p>
              } @else {
                <form class="ask stack" [formGroup]="ask" (ngSubmit)="send()" novalidate>
                  <div class="grid">
                    <div class="field">
                      <label for="ask-name">Your name</label>
                      <input id="ask-name" formControlName="contact_name" autocomplete="name" />
                      @if (errors()['contact_name']; as m) { <span class="field-error">{{ m }}</span> }
                    </div>
                    <div class="field">
                      <label for="ask-phone">Phone</label>
                      <input id="ask-phone" type="tel" formControlName="phone" autocomplete="tel" />
                      @if (errors()['phone']; as m) { <span class="field-error">{{ m }}</span> }
                    </div>
                    <div class="field">
                      <label for="ask-email">Email (or phone)</label>
                      <input id="ask-email" type="email" formControlName="email" autocomplete="email" />
                      @if (errors()['email']; as m) { <span class="field-error">{{ m }}</span> }
                    </div>
                    <div class="field">
                      <label for="ask-learner">Child's name</label>
                      <input id="ask-learner" formControlName="learner_name" />
                    </div>
                    <div class="field full">
                      <label for="ask-place">Interested in (optional)</label>
                      <select id="ask-place" formControlName="place">
                        <option [ngValue]="null">Not sure yet</option>
                        @for (cycle of admissions.cycles; track cycle.id) {
                          @for (place of cycle.places; track place.id) {
                            <option [ngValue]="place.id">{{ place.label }}{{ place.campus_name ? ' · ' + place.campus_name : '' }}</option>
                          }
                        }
                      </select>
                    </div>
                    <div class="field full">
                      <label for="ask-message">Your question</label>
                      <textarea id="ask-message" rows="3" formControlName="message"></textarea>
                    </div>
                  </div>
                  <!-- Left empty by people; bots fill every field. -->
                  <input class="trap" formControlName="website" tabindex="-1" autocomplete="off" aria-hidden="true" />
                  @if (error()) { <p class="field-error" role="alert">{{ error() }}</p> }
                  <div><button type="submit" class="btn btn-secondary" [disabled]="busy()">Send question</button></div>
                </form>
              }
            </section>
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

    .grid {
      display: grid;
      gap: 12px;

      @media (min-width: 640px) {
        grid-template-columns: 1fr 1fr;

        .full {
          grid-column: 1 / -1;
        }
      }
    }

    .trap {
      position: absolute;
      left: -10000px;
      width: 1px;
      height: 1px;
      overflow: hidden;
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
  protected readonly ask = inject(NonNullableFormBuilder).group({
    contact_name: [''],
    phone: [''],
    email: [''],
    learner_name: [''],
    place: [null as string | null],
    message: [''],
    website: [''],
  });
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');
  protected readonly reference = signal('');

  protected send(): void {
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    this.api.post<{ number: string }>('public/enquiries', this.ask.getRawValue()).subscribe({
      next: (sent) => {
        this.busy.set(false);
        this.reference.set(sent.number || 'received');
      },
      error: (err) => {
        this.busy.set(false);
        this.errors.set(fieldErrors(err));
        if (!Object.keys(fieldErrors(err)).length) {
          this.error.set(apiErrorMessage(err));
        }
      },
    });
  }
}
