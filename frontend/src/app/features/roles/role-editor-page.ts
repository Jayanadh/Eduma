import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { Observable, of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { PermissionGroup, RoleItem } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { roleDiff } from './role-diff';

/** A custom role: its name and the permissions it gives, never beyond the editor's own, with a preview of the change
 * and how many people it reaches. */
@Component({
  selector: 'app-role-editor-page',
  imports: [LoadError, PageHeader, ReactiveFormsModule],
  template: `
    <div class="page">
      <app-page-header eyebrow="Roles" [title]="id() ? 'Change role' : 'New role'" backLink="/app/roles" />
      <app-load-error [message]="registry.error() || role.error()" (retry)="registry.reload(); role.reload()" />
      @if (registry.value(); as groups) {
        <form class="card card-strong stack section" [formGroup]="form" (ngSubmit)="save()" novalidate>
          <div class="form-grid">
            <div class="field">
              <label for="role-name">Name</label>
              <input id="role-name" formControlName="name" [attr.aria-invalid]="!!errors()['name']" />
              @if (errors()['name']; as message) { <span class="field-error">{{ message }}</span> }
            </div>
            <div class="field full">
              <label for="role-description">What this role is for (optional)</label>
              <input id="role-description" formControlName="description" />
            </div>
          </div>
          @for (group of groups; track group.group) {
            <fieldset class="perms">
              <legend>{{ group.group }}</legend>
              @for (perm of group.permissions; track perm.name) {
                <label class="check" [for]="'perm-' + perm.name">
                  <input
                    type="checkbox"
                    [id]="'perm-' + perm.name"
                    [checked]="chosen().includes(perm.name)"
                    [disabled]="!auth.can(perm.name)"
                    (change)="toggle(perm.name, $any($event.target).checked)"
                  />
                  <span>
                    {{ perm.label }}
                    @if (!auth.can(perm.name)) { <span class="muted small"> · You don't have this</span> }
                    @else if (perm.institution_only) { <span class="muted small"> · whole institution only</span> }
                  </span>
                </label>
              }
            </fieldset>
          }
          @if (errors()['permissions']; as message) { <p class="field-error">{{ message }}</p> }
          @if (preview(); as change) {
            <p class="notice notice-info" role="status">{{ change }}</p>
          }
          @if (error()) {
            <p class="field-error" role="alert">{{ error() }}</p>
          }
          <div class="form-actions">
            <button type="submit" class="btn btn-primary" [disabled]="busy()">{{ busy() ? 'Saving…' : 'Save role' }}</button>
          </div>
        </form>
      }
    </div>
  `,
  styles: `
    .perms {
      margin: 0;
      padding: 0;
      border: 0;
    }

    legend {
      margin-bottom: 4px;
      font-weight: 800;
    }
  `,
})
export class RoleEditorPage {
  /** The custom role's id; absent for a new role. */
  readonly id = input<string>();
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  protected readonly auth = inject(AuthStore);

  protected readonly registry = load(() => this.api.get<PermissionGroup[]>('institution/permissions'));
  protected readonly role = load(
    (): Observable<RoleItem | null> => (this.id() ? this.api.get<RoleItem>(`institution/roles/${this.id()}`) : of(null)),
    () => this.id(),
  );
  protected readonly form = inject(NonNullableFormBuilder).group({
    name: ['', Validators.required],
    description: [''],
  });
  protected readonly chosen = signal<string[]>([]);
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');

  /** "Adds: … · Removes: … · Affects 3 people", or nothing before a change. */
  protected readonly preview = computed(() => {
    const before = this.role.value()?.permissions ?? [];
    const { added, removed } = roleDiff(before, this.chosen());
    if (!added.length && !removed.length) {
      return '';
    }
    const parts = [];
    if (added.length) {
      parts.push(`Adds: ${this.labels(added)}`);
    }
    if (removed.length) {
      parts.push(`Removes: ${this.labels(removed)}`);
    }
    const count = this.role.value()?.assigned_count ?? 0;
    if (count) {
      parts.push(`Affects ${count} ${count === 1 ? 'person' : 'people'}`);
    }
    return parts.join(' · ');
  });

  constructor() {
    effect(() => {
      const role = this.role.value();
      if (role) {
        this.form.reset({ name: role.label, description: role.description });
        this.chosen.set([...role.permissions]);
      }
    });
  }

  private labels(names: string[]): string {
    const all = (this.registry.value() ?? []).flatMap((group) => group.permissions);
    return names.map((name) => all.find((perm) => perm.name === name)?.label ?? name).join(', ');
  }

  protected toggle(name: string, on: boolean): void {
    this.chosen.update((list) => (on ? [...list, name].sort() : list.filter((item) => item !== name)));
  }

  protected save(): void {
    if (this.busy()) {
      return;
    }
    const role = this.role.value();
    const body = { ...this.form.getRawValue(), permissions: this.chosen() };
    const request = role
      ? this.api.patch<RoleItem>(`institution/roles/${role.id}`, { ...body, version: role.version })
      : this.api.post<RoleItem>('institution/roles', body);
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    request.subscribe({
      next: (saved) => {
        this.toasts.show(`${saved.label} saved.`);
        void this.router.navigateByUrl('/app/roles', { replaceUrl: true });
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
