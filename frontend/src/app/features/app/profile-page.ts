import { Component, effect, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors, isProblem } from '../../core/api-error';
import { CATEGORY_LABELS, InstitutionDetail } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

/** The institution's contact details, which its admin keeps up to date. Names and codes are set by the Eduma team. */
@Component({
  selector: 'app-profile-page',
  imports: [LoadError, PageHeader, ReactiveFormsModule],
  template: `
    <div class="page">
      <app-page-header title="Profile" subtitle="How people reach your office. These details appear at the foot of your public page." />
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as institution) {
        <div class="grid-2 section">
          <form class="card stack" [formGroup]="form" (ngSubmit)="save(institution)" novalidate>
            @if (conflict()) {
              <div class="notice notice-warning" role="alert">
                These details changed while you were editing.
                <button type="button" class="btn btn-secondary btn-sm" (click)="data.reload()">Reload the latest</button>
              </div>
            }
            <div class="field">
              <label for="office-email">Office email</label>
              <input id="office-email" type="email" formControlName="contact_email" />
              @if (errors()['contact_email']; as message) { <span class="field-error">{{ message }}</span> }
            </div>
            <div class="field">
              <label for="office-phone">Office phone</label>
              <input id="office-phone" type="tel" formControlName="contact_phone" />
              @if (errors()['contact_phone']; as message) { <span class="field-error">{{ message }}</span> }
            </div>
            <div class="field">
              <label for="office-address">Address</label>
              <textarea id="office-address" rows="3" formControlName="address"></textarea>
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn-primary" [disabled]="busy() || form.pristine">
                {{ busy() ? 'Saving…' : 'Save' }}
              </button>
            </div>
          </form>
          <section class="card">
            <h2 class="card-title">Set by the Eduma team</h2>
            <dl class="facts">
              <div><dt>Legal name</dt><dd>{{ institution.legal_name }}</dd></div>
              <div><dt>Category</dt><dd>{{ categories[institution.category] }}</dd></div>
              <div><dt>Web address</dt><dd class="url">{{ institution.url }}</dd></div>
            </dl>
          </section>
        </div>
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .facts {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin: 14px 0 0;

      dt {
        color: var(--muted);
        font-size: 13px;
        font-weight: 700;
      }

      dd {
        margin: 0;
        font-weight: 600;
      }
    }
  `,
})
export class ProfilePage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly categories = CATEGORY_LABELS;
  protected readonly data = load(() => this.api.get<InstitutionDetail>('institution'));
  protected readonly form = inject(NonNullableFormBuilder).group({
    contact_email: ['', [Validators.email]],
    contact_phone: [''],
    address: [''],
  });
  protected readonly busy = signal(false);
  protected readonly conflict = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  constructor() {
    effect(() => {
      const institution = this.data.value();
      if (institution) {
        this.form.reset(institution);
        this.conflict.set(false);
      }
    });
  }

  protected save(institution: InstitutionDetail): void {
    if (this.busy()) {
      return;
    }
    this.busy.set(true);
    this.errors.set({});
    this.api
      .patch<InstitutionDetail>('institution', { ...this.form.getRawValue(), version: institution.version })
      .subscribe({
        next: (updated) => {
          this.busy.set(false);
          this.data.value.set(updated);
          this.toasts.show('Details saved.');
        },
        error: (err) => {
          this.busy.set(false);
          this.conflict.set(isProblem(err, 'version_conflict'));
          this.errors.set(fieldErrors(err));
          if (!this.conflict() && !Object.keys(this.errors()).length) {
            this.toasts.show(apiErrorMessage(err), 'danger');
          }
        },
      });
  }
}
