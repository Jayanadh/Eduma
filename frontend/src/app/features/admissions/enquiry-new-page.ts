import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { AdmissionCycle, Enquiry, Page } from '../../core/api/types';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { ENQUIRY_SOURCES } from './enquiries-page';

/** A walk-in, phone or event enquiry recorded by the office. */
@Component({
  selector: 'app-enquiry-new-page',
  imports: [PageHeader, ReactiveFormsModule],
  template: `
    <div class="page">
      <app-page-header eyebrow="Admissions" title="New enquiry" />
      <form class="card stack section" [formGroup]="form" (ngSubmit)="save()" novalidate>
        <div class="field">
          <label for="new-source">Came from</label>
          <select id="new-source" formControlName="source">
            @for (s of sources; track s[0]) { <option [value]="s[0]">{{ s[1] }}</option> }
          </select>
        </div>
        <div class="field">
          <label for="new-name">Contact name</label>
          <input id="new-name" formControlName="contact_name" />
          @if (errors()['contact_name']; as m) { <span class="field-error">{{ m }}</span> }
        </div>
        <div class="field">
          <label for="new-phone">Phone</label>
          <input id="new-phone" type="tel" formControlName="phone" />
          @if (errors()['phone']; as m) { <span class="field-error">{{ m }}</span> }
        </div>
        <div class="field">
          <label for="new-email">Email</label>
          <input id="new-email" type="email" formControlName="email" />
          @if (errors()['email']; as m) { <span class="field-error">{{ m }}</span> }
        </div>
        <div class="field">
          <label for="new-learner">Child's name</label>
          <input id="new-learner" formControlName="learner_name" />
        </div>
        <div class="field">
          <label for="new-place">Interested in</label>
          <select id="new-place" formControlName="place">
            <option [ngValue]="null">Not said</option>
            @for (cycle of cycles.value()?.results ?? []; track cycle.id) {
              @if (cycle.status !== 'draft') {
                @for (place of cycle.places; track place.id) {
                  <option [ngValue]="place.id">{{ cycle.name }} · {{ place.label }}</option>
                }
              }
            }
          </select>
          @if (errors()['place']; as m) { <span class="field-error">{{ m }}</span> }
        </div>
        <div class="field">
          <label for="new-message">What they asked</label>
          <textarea id="new-message" rows="3" formControlName="message"></textarea>
        </div>
        @if (error()) { <p class="field-error" role="alert">{{ error() }}</p> }
        <div class="form-actions"><button type="submit" class="btn btn-primary" [disabled]="busy() || form.invalid">Save enquiry</button></div>
      </form>
    </div>
  `,
})
export class EnquiryNewPage {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  protected readonly sources = ENQUIRY_SOURCES.filter(([key]) => key !== 'website');
  protected readonly cycles = load(() =>
    this.api.get<Page<AdmissionCycle>>('institution/admissions/cycles', { page_size: 200 }),
  );
  protected readonly form = inject(NonNullableFormBuilder).group({
    source: ['walk_in'],
    contact_name: ['', Validators.required],
    phone: [''],
    email: [''],
    learner_name: [''],
    place: [null as string | null],
    message: [''],
  });
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');

  protected save(): void {
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    this.api.post<Enquiry>('institution/admissions/enquiries', this.form.getRawValue()).subscribe({
      next: (made) => {
        this.toasts.show(`${made.number} saved.`);
        void this.router.navigate(['/app/admissions/enquiries', made.id], { replaceUrl: true });
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
