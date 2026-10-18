import { Component, computed, inject, input } from '@angular/core';
import { Router } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { CATEGORY_LABELS, InstitutionDetail } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { CopyUrl } from '../../ui/copy-url';
import { Icon } from '../../ui/icon';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { StatusBadge } from '../../ui/status-badge';
import { ToastService } from '../../ui/toast';
import { UnsavedChanges } from '../../core/unsaved-changes';
import { AuditList } from './audit-list';
import { allowedMoves, lifecycleQuestion, Move } from './lifecycle';
import { InstitutionProfileForm } from './profile-form';

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'activity', label: 'Activity' },
];

/** One institution, for the platform admin: its state and readiness, its details and its history. Its branding is its
 * own admin's to do. */
@Component({
  selector: 'app-institution-page',
  imports: [
    AuditList,
    CopyUrl,
    Icon,
    InstitutionProfileForm,
    LoadError,
    PageHeader,
    StatusBadge,
  ],
  templateUrl: './institution-page.html',
  styleUrl: './institution-page.scss',
})
export class InstitutionPage {
  readonly id = input.required<string>();
  /** ?tab=; the router sets it to undefined when absent. */
  readonly tab = input<string | undefined>();
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  private readonly router = inject(Router);
  private readonly unsaved = inject(UnsavedChanges);

  protected readonly tabs = TABS;
  protected readonly current = computed(() =>
    TABS.some((tab) => tab.key === this.tab()) ? this.tab() : 'overview',
  );
  protected readonly data = load(
    () => this.api.get<InstitutionDetail>(`platform/institutions/${this.id()}`),
    () => this.id(),
  );
  protected readonly moves = computed(() => {
    const institution = this.data.value();
    return institution ? allowedMoves(institution.lifecycle_status) : [];
  });
  protected readonly categoryLabel = computed(() => {
    const institution = this.data.value();
    return institution ? CATEGORY_LABELS[institution.category] : '';
  });
  protected readonly dateTime = dateTime;

  protected async move(move: Move): Promise<void> {
    const institution = this.data.value();
    if (!institution) {
      return;
    }
    const missing = institution.readiness.filter((item) => !item.done).map((item) => item.label);
    const reason = await this.confirm.prompt(
      lifecycleQuestion(move, institution.display_name, missing),
    );
    if (reason === null) {
      return;
    }
    const early = move.label === 'Activate' && missing.length > 0;
    this.api
      .post<InstitutionDetail>(`platform/institutions/${institution.id}/transition`, {
        to: move.to,
        reason,
        override_reason: early ? reason : '',
        version: institution.version,
      })
      .subscribe({
        next: (updated) => {
          this.data.value.set(updated);
          this.toasts.show(
            `${updated.display_name} is now ${this.stateWord(updated.lifecycle_status)}.`,
          );
        },
        error: (err) => {
          this.toasts.show(apiErrorMessage(err), 'danger');
          this.data.reload();
        },
      });
  }

  protected async resetPassword(): Promise<void> {
    const institution = this.data.value();
    const admin = institution?.admin;
    if (!institution || !admin) {
      return;
    }
    const password = await this.confirm.firstPassword(`New first password for ${admin.full_name}`);
    if (password === null) {
      return;
    }
    this.api
      .post<void>(`platform/institutions/${institution.id}/admin-password`, { password })
      .subscribe({
        next: () => {
          this.toasts.show(
            'Password set. Hand it over in person; they will choose their own at sign-in.',
          );
          this.data.reload();
        },
        error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
      });
  }

  protected async openTab(key: string): Promise<void> {
    if (key === this.current() || !(await this.unsaved.confirmLeave())) {
      return;
    }
    void this.router.navigate([], {
      queryParams: { tab: key === 'overview' ? null : key },
      replaceUrl: true,
    });
  }

  private stateWord(status: InstitutionDetail['lifecycle_status']): string {
    return {
      setup: 'being set up',
      active: 'active',
      suspended: 'suspended',
      archived: 'archived',
    }[status];
  }
}
