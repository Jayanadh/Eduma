import { Component, computed, DestroyRef, effect, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { ApplicantApplication } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { UnsavedChanges } from '../../core/unsaved-changes';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from './portal-frame';

type Answer = string | boolean | null;

/**
 * One application, as its family sees it: the form while it can be changed (learner, parent or guardian, questions,
 * documents), what is still missing, and the next step the stage allows — submit, accept an offer or withdraw.
 */
@Component({
  selector: 'app-application-form-page',
  imports: [LoadError, PortalFrame, ReactiveFormsModule],
  template: `
    <app-portal-frame [heading]="heading()">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as a) {
        <p class="muted">{{ a.cycle.name }} · {{ a.place.label }}{{ a.place.campus_name ? ' · ' + a.place.campus_name : '' }}{{ a.number ? ' · ' + a.number : '' }}</p>
        <p><span class="badge badge-info">{{ a.stage_label }}</span></p>

        @if (a.stage === 'needs_information') {
          <p class="notice notice-warning" role="status"><strong>The school asks:</strong> {{ a.information_request }}</p>
        }
        @if (a.stage === 'rejected' && a.decision_reason) {
          <p class="notice notice-info">{{ a.decision_reason }}</p>
        }
        @if (a.stage === 'offered') {
          <section class="card card-strong stack">
            <h2 class="card-title">A place is offered</h2>
            <p>{{ a.place.label }} is offered to {{ a.learner_name }}. Accept by {{ date(a.offer_expires_on) }}.</p>
            <div class="form-actions">
              <button type="button" class="btn btn-primary" [disabled]="busy()" (click)="step(a, 'accept', 'Offer accepted.')">Accept the offer</button>
            </div>
          </section>
        }
        @if (a.stage === 'offer_expired') {
          <p class="notice notice-warning">The offer expired on {{ date(a.offer_expires_on) }}. Contact the school if you still want the place.</p>
        }
        @if (a.stage === 'accepted') {
          <p class="notice notice-info">You accepted the place. The school will complete the enrollment.</p>
        }
        @if (a.stage === 'enrolled') {
          <p class="notice notice-info">{{ a.learner_name }} is enrolled. The school will share the student's own sign-in.</p>
        }

        @if (editable()) {
          <form class="stack" [formGroup]="form" (ngSubmit)="save(a)" novalidate>
            <section class="card stack">
              <h2 class="card-title">The learner</h2>
              <div class="form-grid">
                <div class="field">
                  <label for="learner-name">Full name</label>
                  <input id="learner-name" formControlName="learner_name" />
                  @if (problem('learner_name'); as m) { <span class="field-error">{{ m }}</span> }
                </div>
                <div class="field">
                  <label for="learner-dob">Date of birth</label>
                  <input id="learner-dob" type="date" formControlName="date_of_birth" />
                  @if (problem('date_of_birth'); as m) { <span class="field-error">{{ m }}</span> }
                </div>
                <div class="field full">
                  <label for="learner-previous">Previous school (if any)</label>
                  <input id="learner-previous" formControlName="previous_school" />
                </div>
              </div>
            </section>
            <section class="card stack">
              <h2 class="card-title">Parent or guardian</h2>
              <div class="form-grid">
                <div class="field">
                  <label for="guardian-name">Full name</label>
                  <input id="guardian-name" formControlName="guardian_name" />
                  @if (problem('guardian_name'); as m) { <span class="field-error">{{ m }}</span> }
                </div>
                <div class="field">
                  <label for="guardian-relationship">Relationship to the learner</label>
                  <input id="guardian-relationship" formControlName="guardian_relationship" placeholder="Mother, father, guardian…" />
                  @if (problem('guardian_relationship'); as m) { <span class="field-error">{{ m }}</span> }
                </div>
                <div class="field">
                  <label for="guardian-phone">Phone</label>
                  <input id="guardian-phone" type="tel" formControlName="guardian_phone" />
                  @if (problem('guardian_phone'); as m) { <span class="field-error">{{ m }}</span> }
                </div>
                <div class="field">
                  <label for="guardian-email">Email (optional)</label>
                  <input id="guardian-email" type="email" formControlName="guardian_email" />
                  @if (problem('guardian_email'); as m) { <span class="field-error">{{ m }}</span> }
                </div>
                <div class="field full">
                  <label for="guardian-address">Address</label>
                  <textarea id="guardian-address" rows="2" formControlName="address"></textarea>
                  @if (problem('address'); as m) { <span class="field-error">{{ m }}</span> }
                </div>
              </div>
            </section>
            @if (a.questions.length) {
              <section class="card stack">
                <h2 class="card-title">Questions</h2>
                @for (q of a.questions; track q.code) {
                  <div class="field">
                    <label [for]="'q-' + q.code">{{ q.label }}{{ q.required ? '' : ' (optional)' }}</label>
                    @switch (q.kind) {
                      @case ('long_text') {
                        <textarea [id]="'q-' + q.code" rows="3" [value]="text(q.code)" (input)="answer(q.code, $any($event.target).value)"></textarea>
                      }
                      @case ('date') {
                        <input [id]="'q-' + q.code" type="date" [value]="text(q.code)" (input)="answer(q.code, $any($event.target).value)" />
                      }
                      @case ('choice') {
                        <select [id]="'q-' + q.code" (change)="answer(q.code, $any($event.target).value)">
                          <option value="">Choose</option>
                          @for (option of q.options; track option) {
                            <option [value]="option" [selected]="answers()[q.code] === option">{{ option }}</option>
                          }
                        </select>
                      }
                      @case ('yes_no') {
                        <select [id]="'q-' + q.code" (change)="answer(q.code, $any($event.target).value === '' ? null : $any($event.target).value === 'yes')">
                          <option value="">Choose</option>
                          <option value="yes" [selected]="answers()[q.code] === true">Yes</option>
                          <option value="no" [selected]="answers()[q.code] === false">No</option>
                        </select>
                      }
                      @default {
                        <input [id]="'q-' + q.code" [value]="text(q.code)" (input)="answer(q.code, $any($event.target).value)" />
                      }
                    }
                    @if (q.help) { <span class="field-hint">{{ q.help }}</span> }
                    @if (problem('answers.' + q.code); as m) { <span class="field-error">{{ m }}</span> }
                  </div>
                }
              </section>
            }
            <div class="form-actions">
              <button type="submit" class="btn btn-secondary" [disabled]="busy() || !dirty()">Save</button>
            </div>
          </form>

          <section class="card stack">
            <h2 class="card-title">Documents</h2>
            <p class="muted small">PDF, JPEG or PNG, up to 5 MB each.</p>
            @for (r of a.requirements; track r.code) {
              <div class="field doc">
                <label [for]="'doc-' + r.code">{{ r.label }}{{ r.required ? '' : ' (optional)' }}</label>
                @if (documentFor(r.code); as d) {
                  <span class="small">{{ d.original_name }} ·
                    @if (d.status === 'rejected') { <strong class="danger">Needs replacing: {{ d.review_note }}</strong> }
                    @else if (d.status === 'verified') { checked } @else { uploaded }
                  </span>
                }
                <input [id]="'doc-' + r.code" type="file" accept="application/pdf,image/jpeg,image/png" (change)="upload(a, r.code, $event)" />
                @if (problem('documents.' + r.code); as m) { <span class="field-error">{{ m }}</span> }
              </div>
            }
          </section>

          @if (missingList().length) {
            <section class="notice notice-warning" role="status">
              <strong>Before you can submit:</strong>
              <ul>
                @for (item of missingList(); track item) { <li>{{ item }}</li> }
              </ul>
            </section>
          }
          @if (error()) { <p class="field-error" role="alert">{{ error() }}</p> }
          <div class="form-actions">
            <button type="button" class="btn btn-primary" [disabled]="busy() || dirty() || missingList().length > 0" (click)="step(a, 'submit', 'Application submitted.')">Submit application</button>
            @if (dirty()) { <span class="muted small">Save your changes first.</span> }
          </div>
        } @else if (a.submitted_at) {
          <section class="card stack">
            <h2 class="card-title">What you sent</h2>
            <dl class="facts">
              <div><dt>Learner</dt><dd>{{ a.learner_name }} · born {{ date(a.date_of_birth) }}</dd></div>
              <div><dt>Parent or guardian</dt><dd>{{ a.guardian_name }} ({{ a.guardian_relationship }}) · {{ a.guardian_phone }}</dd></div>
              <div><dt>Documents</dt><dd>{{ a.documents.length }} uploaded</dd></div>
            </dl>
          </section>
        }
        @if (a.allowed_actions.includes('withdraw')) {
          <div class="form-actions">
            <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="withdraw(a)">Withdraw this application</button>
          </div>
        }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </app-portal-frame>
  `,
  styles: `
    .doc input[type='file'] {
      margin-top: 4px;
    }

    .danger {
      color: var(--danger);
    }
  `,
})
export class ApplicationFormPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  private readonly unsaved = inject(UnsavedChanges);
  protected readonly date = date;

  protected readonly data = load(
    () => this.api.get<ApplicantApplication>(`applicant/applications/${this.id()}`),
    () => this.id(),
  );
  protected readonly form = inject(NonNullableFormBuilder).group({
    learner_name: [''],
    date_of_birth: [''],
    previous_school: [''],
    guardian_name: [''],
    guardian_relationship: [''],
    guardian_phone: [''],
    guardian_email: [''],
    address: [''],
  });
  protected readonly answers = signal<Record<string, Answer>>({});
  private readonly answersTouched = signal(false);
  private readonly formTouched = signal(false);
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');

  protected readonly heading = computed(() => {
    const a = this.data.value();
    return a?.learner_name ? `Application for ${a.learner_name}` : 'Your application';
  });
  protected readonly editable = computed(() => this.data.value()?.allowed_actions.includes('edit') ?? false);
  protected readonly dirty = computed(() => this.formTouched() || this.answersTouched());
  protected readonly missingList = computed(() => Object.values(this.data.value()?.missing ?? {}));

  constructor() {
    effect(() => {
      const a = this.data.value();
      if (a) {
        this.form.reset({
          learner_name: a.learner_name,
          date_of_birth: a.date_of_birth ?? '',
          previous_school: a.previous_school,
          guardian_name: a.guardian_name,
          guardian_relationship: a.guardian_relationship,
          guardian_phone: a.guardian_phone,
          guardian_email: a.guardian_email,
          address: a.address,
        });
        this.answers.set({ ...a.answers });
        this.answersTouched.set(false);
        this.formTouched.set(false);
      }
    });
    this.form.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.formTouched.set(this.form.dirty));
    effect(() => this.unsaved.dirty.set(this.dirty()));
    inject(DestroyRef).onDestroy(() => this.unsaved.dirty.set(false));
  }

  /** The server's word on a field, else what it says is still missing. */
  protected problem(field: string): string {
    return this.errors()[field] ?? '';
  }

  protected text(code: string): string {
    const value = this.answers()[code];
    return typeof value === 'string' ? value : '';
  }

  protected answer(code: string, value: Answer): void {
    this.answers.update((all) => ({ ...all, [code]: value }));
    this.answersTouched.set(true);
  }

  protected documentFor(code: string) {
    return this.data.value()?.documents.find((d) => d.requirement === code);
  }

  private settle(updated: ApplicantApplication, message: string): void {
    this.busy.set(false);
    this.data.value.set(updated);
    if (message) {
      this.toasts.show(message);
    }
  }

  private failed(err: unknown): void {
    this.busy.set(false);
    const fields = fieldErrors(err);
    this.errors.set(fields);
    if (!Object.keys(fields).length) {
      this.error.set(apiErrorMessage(err));
    }
  }

  protected save(a: ApplicantApplication): void {
    const values = this.form.getRawValue();
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    const body = { ...values, date_of_birth: values.date_of_birth || null, answers: this.answers(), version: a.version };
    this.api.patch<ApplicantApplication>(`applicant/applications/${a.id}`, body).subscribe({
      next: (updated) => this.settle(updated, 'Saved.'),
      error: (err) => this.failed(err),
    });
  }

  protected upload(a: ApplicantApplication, code: string, event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) {
      return;
    }
    this.busy.set(true);
    this.errors.set({});
    this.api
      .upload<ApplicantApplication>(`applicant/applications/${a.id}/documents`, 'file', file, { requirement: code })
      .subscribe({
        next: (updated) => this.settle(updated, `${file.name} uploaded.`),
        error: (err) => {
          const fields = fieldErrors(err);
          this.failed(err);
          if (fields['file']) {
            this.errors.update((all) => ({ ...all, [`documents.${code}`]: fields['file'] }));
          }
        },
      });
  }

  protected step(a: ApplicantApplication, action: 'submit' | 'accept' | 'withdraw', message: string): void {
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    this.api.post<ApplicantApplication>(`applicant/applications/${a.id}/${action}`, { version: a.version }).subscribe({
      next: (updated) => this.settle(updated, message),
      error: (err) => this.failed(err),
    });
  }

  protected async withdraw(a: ApplicantApplication): Promise<void> {
    const yes = await this.confirm.ask({
      title: 'Withdraw this application?',
      message: 'The school stops considering it. You cannot undo this; you can start a new application while admissions are open.',
      confirmLabel: 'Withdraw',
      tone: 'danger',
    });
    if (yes) {
      this.step(a, 'withdraw', 'Application withdrawn.');
    }
  }
}
