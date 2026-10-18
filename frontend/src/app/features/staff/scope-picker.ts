import { Component, input, model } from '@angular/core';
import { ScopeType } from '../../core/api/types';

export type ScopeValue = { scope_type: ScopeType; campus: string | null; department: string | null };
type Option = { id: string; name: string };

/** Where a role applies: the whole institution, one campus or one department. */
@Component({
  selector: 'app-scope-picker',
  template: `
    <div class="field">
      <label for="scope-type">For</label>
      <select id="scope-type" (change)="setType($any($event.target).value)">
        <option value="institution" [selected]="value().scope_type === 'institution'">The whole institution</option>
        <option value="campus" [selected]="value().scope_type === 'campus'">One campus</option>
        <option value="department" [selected]="value().scope_type === 'department'">One department</option>
      </select>
      @if (errors()['scope_type']; as message) { <span class="field-error">{{ message }}</span> }
    </div>
    @if (value().scope_type === 'campus') {
      <div class="field">
        <label for="scope-campus">Campus</label>
        <select id="scope-campus" (change)="value.set({ scope_type: 'campus', campus: $any($event.target).value || null, department: null })">
          <option value="">Choose a campus</option>
          @for (option of campuses(); track option.id) {
            <option [value]="option.id" [selected]="option.id === value().campus">{{ option.name }}</option>
          }
        </select>
        @if (errors()['campus']; as message) { <span class="field-error">{{ message }}</span> }
      </div>
    }
    @if (value().scope_type === 'department') {
      <div class="field">
        <label for="scope-department">Department</label>
        <select id="scope-department" (change)="value.set({ scope_type: 'department', campus: null, department: $any($event.target).value || null })">
          <option value="">Choose a department</option>
          @for (option of departments(); track option.id) {
            <option [value]="option.id" [selected]="option.id === value().department">{{ option.name }}</option>
          }
        </select>
        @if (errors()['department']; as message) { <span class="field-error">{{ message }}</span> }
      </div>
    }
  `,
  styles: `
    :host {
      display: contents;
    }
  `,
})
export class ScopePicker {
  readonly campuses = input.required<Option[]>();
  readonly departments = input.required<Option[]>();
  readonly value = model.required<ScopeValue>();
  readonly errors = input<Record<string, string>>({});

  protected setType(scope_type: ScopeType): void {
    this.value.set({ scope_type, campus: null, department: null });
  }
}
