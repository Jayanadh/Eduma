import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { Page, PermissionGroup, RoleItem } from '../../core/api/types';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Icon } from '../../ui/icon';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { StatusBadge } from '../../ui/status-badge';
import { ToastService } from '../../ui/toast';

/** Built-in roles (the same everywhere, growing as modules arrive) and the institution's own custom roles. */
@Component({
  selector: 'app-roles-page',
  imports: [Icon, LoadError, PageHeader, Pager, RouterLink, StatusBadge],
  template: `
    <div class="page">
      <app-page-header title="Roles" subtitle="What each role allows. Give roles to people from their Staff page.">
        <a class="btn btn-primary" routerLink="/app/roles/new"><app-icon name="plus" [size]="18" /> New role</a>
      </app-page-header>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as result) {
        <div class="stack section">
          @for (role of result.results; track role.id) {
            <article class="card stack role">
              <div class="role-head">
                <h2 class="card-title">{{ role.label }}</h2>
                @if (role.builtin) {
                  <span class="badge badge-info">Built in</span>
                } @else if (!role.is_active) {
                  <app-status-badge status="archived" label="Archived" />
                }
                <span class="muted small count">{{ role.assigned_count }} {{ role.assigned_count === 1 ? 'person' : 'people' }}</span>
              </div>
              @if (role.description) {
                <p class="muted">{{ role.description }}</p>
              }
              <ul class="perms">
                @for (name of role.permissions; track name) {
                  <li><app-icon name="check" [size]="14" /> {{ label(name) }}</li>
                } @empty {
                  <li class="muted small">Signs in and sees the home page; nothing else yet.</li>
                }
              </ul>
              @if (!role.builtin && role.is_active) {
                <div class="form-actions">
                  <a class="btn btn-secondary btn-sm" [routerLink]="['/app/roles', role.id]"><app-icon name="pencil" [size]="16" /> Change</a>
                  <button type="button" class="btn btn-secondary btn-sm" (click)="archive(role)">Archive</button>
                </div>
              }
            </article>
          }
        </div>
        <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .role-head {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 12px;
    }

    .count {
      margin-left: auto;
    }

    .perms {
      display: grid;
      gap: 6px;
      margin: 0;
      padding: 0;
      list-style: none;

      li {
        display: flex;
        align-items: center;
        gap: 8px;
      }
    }
  `,
})
export class RolesPage {
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  protected readonly page = signal(1);
  protected readonly data = load(
    () => this.api.get<Page<RoleItem>>('institution/roles', { page: this.page() }),
    () => this.page(),
  );
  private readonly registry = load(() => this.api.get<PermissionGroup[]>('institution/permissions'));

  protected label(name: string): string {
    const all = (this.registry.value() ?? []).flatMap((group) => group.permissions);
    return all.find((perm) => perm.name === name)?.label ?? name;
  }

  protected async archive(role: RoleItem): Promise<void> {
    const yes = await this.confirm.ask({
      title: `Archive ${role.label}?`,
      message: 'It can no longer be given. People must not hold it when you archive it.',
      confirmLabel: 'Archive',
      tone: 'danger',
    });
    if (!yes) {
      return;
    }
    this.api.patch<RoleItem>(`institution/roles/${role.id}`, { version: role.version, is_active: false }).subscribe({
      next: () => {
        this.toasts.show(`${role.label} archived.`);
        this.data.reload();
      },
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }
}
