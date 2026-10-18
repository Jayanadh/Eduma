import { Component, effect, inject, input, output, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { Campus } from '../../core/api/types';

/** Add a campus (campus null) or change one. */
@Component({
  selector: 'app-campus-form',
  imports: [ReactiveFormsModule],
  template: `
    <form class="stack" [formGroup]="form" (ngSubmit)="save()" novalidate>
      <h3 class="card-title">{{ campus() ? 'Change ' + campus()!.name : 'Add a campus' }}</h3>
      <div class="form-grid">
        <div class="field">
          <label for="campus-code">Code</label>
          <input id="campus-code" formControlName="code" autocapitalize="characters" spellcheck="false" [attr.aria-invalid]="!!errors()['code']" />
          @if (errors()['code']; as message) {
            <span class="field-error">{{ message }}</span>
          } @else {
            <span class="field-hint">Short, such as MAIN or CITY.</span>
          }
        </div>
        <div class="field">
          <label for="campus-name">Name</label>
          <input id="campus-name" formControlName="name" [attr.aria-invalid]="!!errors()['name']" />
          @if (errors()['name']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        <div class="field full">
          <label for="campus-address">Address (optional)</label>
          <textarea id="campus-address" formControlName="address" rows="2"></textarea>
        </div>
        @if (campus()) {
          <label class="check full"><input type="checkbox" formControlName="is_active" /> Active</label>
        }
      </div>
      @if (error()) {
        <p class="field-error" role="alert">{{ error() }}</p>
      }
      <div class="form-actions">
        <button type="submit" class="btn btn-primary" [disabled]="busy()">{{ busy() ? 'Saving…' : 'Save campus' }}</button>
        <button type="button" class="btn btn-secondary" (click)="cancelled.emit()">Cancel</button>
      </div>
    </form>
  `,
})
export class CampusForm {
  readonly campus = input.required<Campus | null>();
  readonly saved = output<Campus>();
  readonly cancelled = output();
  private readonly api = inject(Api);

  protected readonly form = inject(NonNullableFormBuilder).group({
    code: ['', Validators.required],
    name: ['', Validators.required],
    address: [''],
    is_active: [true],
  });
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');

  constructor() {
    effect(() => {
      const campus = this.campus();
      this.form.reset(campus ?? { code: '', name: '', address: '', is_active: true });
      this.errors.set({});
      this.error.set('');
    });
  }

  protected save(): void {
    if (this.busy()) {
      return;
    }
    const campus = this.campus();
    const { code, name, address, is_active } = this.form.getRawValue();
    const request = campus
      ? this.api.patch<Campus>(`institution/campuses/${campus.id}`, {
          version: campus.version,
          code,
          name,
          address,
          is_active,
        })
      : this.api.post<Campus>('institution/campuses', { code, name, address });
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    request.subscribe({
      next: (result) => {
        this.busy.set(false);
        this.saved.emit(result);
      },
      error: (err) => {
        this.busy.set(false);
        const fields = fieldErrors(err);
        this.errors.set(fields);
        if (!Object.keys(fields).length) {
          this.error.set(apiErrorMessage(err));
        }
      },
    });
  }
}
