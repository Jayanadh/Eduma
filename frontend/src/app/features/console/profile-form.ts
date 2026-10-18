import { Component, effect, inject, input, output, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors, isProblem } from '../../core/api-error';
import { CATEGORY_LABELS, InstitutionDetail } from '../../core/api/types';
import { COUNTRIES, CURRENCIES, TIME_ZONES, withCurrent } from '../../core/locales';
import { ToastService } from '../../ui/toast';

/**
 * The platform admin's edit of an institution's details. The web address can change only while it is being set up; its
 * own domain, any time.
 */
@Component({
  selector: 'app-institution-profile-form',
  imports: [ReactiveFormsModule],
  template: `
    <form class="stack" [formGroup]="form" (ngSubmit)="save()" novalidate>
      @if (conflict()) {
        <div class="notice notice-warning" role="alert">
          This record changed while you were editing.
          <button type="button" class="btn btn-secondary btn-sm" (click)="reload.emit()">Reload the latest</button>
        </div>
      }
      <div class="form-grid">
        <div class="field full">
          <label for="p-display">Name</label>
          <input id="p-display" formControlName="display_name" />
          @if (errors()['display_name']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        <div class="field full">
          <label for="p-legal">Legal name</label>
          <input id="p-legal" formControlName="legal_name" />
        </div>
        <div class="field">
          <label for="p-category">Category</label>
          <select id="p-category" formControlName="category">
            @for (option of categories; track option[0]) {
              <option [value]="option[0]">{{ option[1] }}</option>
            }
          </select>
        </div>
        <div class="field">
          <label for="p-slug">Web address</label>
          <input id="p-slug" formControlName="slug" autocapitalize="none" spellcheck="false" />
          @if (errors()['slug']; as message) {
            <span class="field-error">{{ message }}</span>
          } @else if (form.controls.slug.disabled) {
            <span class="field-hint">Fixed once the institution is activated.</span>
          }
        </div>
        <div class="field full">
          <label for="p-domain">Own domain (optional)</label>
          <input id="p-domain" formControlName="custom_domain" placeholder="www.dps.edu.in" autocapitalize="none" spellcheck="false" />
          @if (errors()['custom_domain']; as message) {
            <span class="field-error">{{ message }}</span>
          } @else {
            <span class="field-hint">
              When the institution buys a domain, point it at Eduma and enter it here: its links, page and sign-in then
              use it. Its Eduma address keeps working. Leave empty to use the Eduma address.
            </span>
          }
        </div>
        <div class="field">
          <label for="p-email">Office email</label>
          <input id="p-email" type="email" formControlName="contact_email" />
          @if (errors()['contact_email']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        <div class="field">
          <label for="p-phone">Office phone</label>
          <input id="p-phone" type="tel" formControlName="contact_phone" />
        </div>
        <div class="field full">
          <label for="p-address">Address</label>
          <textarea id="p-address" formControlName="address" rows="3"></textarea>
        </div>
        <div class="field">
          <label for="p-board">Board or affiliation code</label>
          <input id="p-board" formControlName="board_affiliation_code" />
        </div>
        <div class="field">
          <label for="p-udise">UDISE+ code</label>
          <input id="p-udise" formControlName="udise_code" />
          @if (errors()['udise_code']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        <div class="field">
          <label for="p-aishe">AISHE code</label>
          <input id="p-aishe" formControlName="aishe_code" />
          @if (errors()['aishe_code']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        <div class="field">
          <label for="p-country">Country</label>
          <select id="p-country" formControlName="country_code">
            @for (option of choices(countries, 'country_code'); track option.code) {
              <option [value]="option.code">{{ option.label }}</option>
            }
          </select>
        </div>
        <div class="field">
          <label for="p-timezone">Time zone</label>
          <select id="p-timezone" formControlName="timezone">
            @for (option of choices(timeZones, 'timezone'); track option.code) {
              <option [value]="option.code">{{ option.label }}</option>
            }
          </select>
          @if (errors()['timezone']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        <div class="field">
          <label for="p-currency">Currency</label>
          <select id="p-currency" formControlName="base_currency">
            @for (option of choices(currencies, 'base_currency'); track option.code) {
              <option [value]="option.code">{{ option.label }}</option>
            }
          </select>
        </div>
      </div>
      <div class="form-actions">
        <button type="submit" class="btn btn-primary" [disabled]="busy() || form.pristine">
          {{ busy() ? 'Saving…' : 'Save details' }}
        </button>
      </div>
    </form>
  `,
})
export class InstitutionProfileForm {
  readonly institution = input.required<InstitutionDetail>();
  readonly saved = output<InstitutionDetail>();
  readonly reload = output();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);

  protected readonly categories = Object.entries(CATEGORY_LABELS);
  protected readonly countries = COUNTRIES;
  protected readonly timeZones = TIME_ZONES;
  protected readonly currencies = CURRENCIES;
  protected readonly form = inject(NonNullableFormBuilder).group({
    display_name: ['', Validators.required],
    legal_name: ['', Validators.required],
    category: [''],
    slug: [''],
    custom_domain: [''],
    contact_email: [''],
    contact_phone: [''],
    address: [''],
    board_affiliation_code: [''],
    udise_code: [''],
    aishe_code: [''],
    country_code: [''],
    timezone: [''],
    base_currency: [''],
  });
  protected readonly busy = signal(false);
  protected readonly conflict = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  constructor() {
    // Fresh values whenever the institution is (re)loaded.
    effect(() => {
      const institution = this.institution();
      this.form.reset(institution);
      if (institution.lifecycle_status === 'setup') {
        this.form.controls.slug.enable();
      } else {
        this.form.controls.slug.disable();
      }
      this.conflict.set(false);
      this.errors.set({});
    });
  }

  /** A list of choices that always holds the institution's saved value. */
  protected choices(list: typeof COUNTRIES, field: 'country_code' | 'timezone' | 'base_currency') {
    return withCurrent(list, this.institution()[field]);
  }

  protected save(): void {
    if (this.busy() || this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const changes: Record<string, string> = {};
    for (const [name, control] of Object.entries(this.form.controls)) {
      if (control.dirty && control.enabled) {
        changes[name] = control.value;
      }
    }
    this.busy.set(true);
    this.errors.set({});
    this.api
      .patch<InstitutionDetail>(`platform/institutions/${this.institution().id}`, {
        ...changes,
        version: this.institution().version,
      })
      .subscribe({
        next: (updated) => {
          this.busy.set(false);
          this.toasts.show('Details saved.');
          this.saved.emit(updated);
        },
        error: (err) => {
          this.busy.set(false);
          this.conflict.set(isProblem(err, 'version_conflict'));
          this.errors.set(fieldErrors(err));
          if (!this.conflict()) {
            this.toasts.show(apiErrorMessage(err), 'danger');
          }
        },
      });
  }
}
