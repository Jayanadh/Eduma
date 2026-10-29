import { Component, effect, inject, input, output, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors, isProblem } from '../../core/api-error';
import { InstitutionDetail, ModuleInfo } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { ToastService } from '../../ui/toast';
import { ModulePicker } from './module-picker';

/** The platform admin's record of which modules an institution's plan includes. */
@Component({
  selector: 'app-modules-tab',
  imports: [LoadError, ModulePicker],
  template: `
    <section class="card stack">
      <h2 class="card-title">Modules in the plan</h2>
      <p class="muted small">What the institution may use. Its admin switches each one on in Settings, and it then appears in their menu.</p>
      <app-load-error [message]="catalogue.error()" (retry)="catalogue.reload()" />
      @if (catalogue.value(); as modules) {
        <app-module-picker [catalogue]="modules" [(selected)]="chosen" [disabled]="busy()" />
      }
      @if (conflict()) {
        <div class="notice notice-warning" role="alert">
          This institution changed while you were editing.
          <button type="button" class="btn btn-secondary btn-sm" (click)="reload.emit()">Reload the latest</button>
        </div>
      } @else if (error()) {
        <p class="field-error" role="alert">{{ error() }}</p>
      }
      <div class="form-actions">
        <button type="button" class="btn btn-primary" [disabled]="busy()" (click)="save()">
          {{ busy() ? 'Saving…' : 'Save modules' }}
        </button>
      </div>
    </section>
  `,
})
export class ModulesTab {
  readonly institution = input.required<InstitutionDetail>();
  readonly saved = output<InstitutionDetail>();
  readonly reload = output();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);

  protected readonly catalogue = load(() => this.api.get<ModuleInfo[]>('platform/modules'));
  readonly chosen = signal<string[]>([]);
  protected readonly busy = signal(false);
  protected readonly conflict = signal(false);
  protected readonly error = signal('');

  constructor() {
    effect(() => {
      this.chosen.set([...this.institution().modules]);
      this.conflict.set(false);
      this.error.set('');
    });
  }

  save(): void {
    if (this.busy()) {
      return;
    }
    const { id, version } = this.institution();
    this.busy.set(true);
    this.error.set('');
    this.api.patch<InstitutionDetail>(`platform/institutions/${id}`, { version, modules: this.chosen() }).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.toasts.show('Modules saved.');
        this.saved.emit(updated);
      },
      error: (err) => {
        this.busy.set(false);
        this.conflict.set(isProblem(err, 'version_conflict'));
        this.error.set(fieldErrors(err)['modules'] ?? apiErrorMessage(err));
      },
    });
  }
}
