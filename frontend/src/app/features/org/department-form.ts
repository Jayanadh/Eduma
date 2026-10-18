import { Component, computed, effect, inject, input, output, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { Campus, Department } from '../../core/api/types';

/** The ids of every department below `id` in `all`. */
function below(id: string, all: readonly Department[]): Set<string> {
  const found = new Set<string>();
  const todo = [id];
  while (todo.length) {
    const parent = todo.pop();
    for (const department of all) {
      if (department.parent?.id === parent && !found.has(department.id)) {
        found.add(department.id);
        todo.push(department.id);
      }
    }
  }
  return found;
}

/** Add a department (department null) or change one. Under a parent it takes the parent's campus. */
@Component({
  selector: 'app-department-form',
  imports: [ReactiveFormsModule],
  template: `
    <form class="stack" [formGroup]="form" (ngSubmit)="save()" novalidate>
      <h3 class="card-title">{{ department() ? 'Change ' + department()!.name : 'Add a department' }}</h3>
      <div class="form-grid">
        <div class="field">
          <label for="department-code">Code</label>
          <input id="department-code" formControlName="code" autocapitalize="characters" spellcheck="false" [attr.aria-invalid]="!!errors()['code']" />
          @if (errors()['code']; as message) {
            <span class="field-error">{{ message }}</span>
          } @else {
            <span class="field-hint">Short, such as SCI or PHY.</span>
          }
        </div>
        <div class="field">
          <label for="department-name">Name</label>
          <input id="department-name" formControlName="name" [attr.aria-invalid]="!!errors()['name']" />
          @if (errors()['name']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        <div class="field">
          <label for="department-parent">Part of</label>
          <select id="department-parent" formControlName="parent">
            <option value="">None</option>
            @for (option of parents(); track option.id) {
              <option [value]="option.id">{{ option.name }}</option>
            }
          </select>
          @if (errors()['parent']; as message) { <span class="field-error">{{ message }}</span> }
        </div>
        @if (!parent()) {
          <div class="field">
            <label for="department-campus">Campus</label>
            <select id="department-campus" formControlName="campus">
              <option value="">No particular campus</option>
              @for (option of campuses(); track option.id) {
                <option [value]="option.id">{{ option.name }}</option>
              }
            </select>
            @if (errors()['campus']; as message) { <span class="field-error">{{ message }}</span> }
          </div>
        }
        @if (department()) {
          <label class="check full"><input type="checkbox" formControlName="is_active" /> Active</label>
        }
      </div>
      @if (error()) {
        <p class="field-error" role="alert">{{ error() }}</p>
      }
      <div class="form-actions">
        <button type="submit" class="btn btn-primary" [disabled]="busy()">{{ busy() ? 'Saving…' : 'Save department' }}</button>
        <button type="button" class="btn btn-secondary" (click)="cancelled.emit()">Cancel</button>
      </div>
    </form>
  `,
})
export class DepartmentForm {
  readonly department = input.required<Department | null>();
  /** Active campuses to choose from. */
  readonly campuses = input.required<Campus[]>();
  /** Every department, for the parent choice. */
  readonly departments = input.required<Department[]>();
  readonly saved = output<Department>();
  readonly cancelled = output();
  private readonly api = inject(Api);

  protected readonly form = inject(NonNullableFormBuilder).group({
    code: ['', Validators.required],
    name: ['', Validators.required],
    parent: [''],
    campus: [''],
    is_active: [true],
  });
  protected readonly parent = toSignal(this.form.controls.parent.valueChanges, { initialValue: '' });
  /** Active departments other than this one and those below it. */
  protected readonly parents = computed(() => {
    const self = this.department();
    const excluded = self ? below(self.id, this.departments()).add(self.id) : new Set<string>();
    return this.departments().filter((option) => option.is_active && !excluded.has(option.id));
  });
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');

  constructor() {
    effect(() => {
      const department = this.department();
      this.form.reset({
        code: department?.code ?? '',
        name: department?.name ?? '',
        parent: department?.parent?.id ?? '',
        campus: department?.campus?.id ?? '',
        is_active: department?.is_active ?? true,
      });
      this.errors.set({});
      this.error.set('');
    });
  }

  protected save(): void {
    if (this.busy()) {
      return;
    }
    const department = this.department();
    const { code, name, parent, campus, is_active } = this.form.getRawValue();
    const body = { code, name, parent: parent || null, campus: parent ? null : campus || null };
    const request = department
      ? this.api.patch<Department>(`institution/departments/${department.id}`, {
          ...body,
          is_active,
          version: department.version,
        })
      : this.api.post<Department>('institution/departments', body);
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
