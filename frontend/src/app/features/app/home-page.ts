import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { Approvals, InstitutionDetail } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { load } from '../../core/load';
import { MODULE_LABELS } from '../../core/modules';
import { date } from '../../core/format';
import { CopyUrl } from '../../ui/copy-url';
import { Icon } from '../../ui/icon';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { StatusBadge } from '../../ui/status-badge';

/** Where a readiness item can be done in the workspace. */
const FIX_AT: Readonly<Record<string, string>> = { site_published: '/app/site', contacts: '/app/profile' };

/** The institution's workspace home: its state, what is left before it goes live, and its web address. */
@Component({
  selector: 'app-home-page',
  imports: [CopyUrl, Icon, LoadError, PageHeader, RouterLink, StatusBadge],
  template: `
    <div class="page">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as institution) {
        <app-page-header [eyebrow]="'Hello, ' + auth.firstName()" [title]="institution.display_name">
          <app-status-badge [status]="institution.lifecycle_status" />
        </app-page-header>
        @if (institution.academic_year; as year) {
          <p class="muted section">Academic year {{ year.label }} ({{ date(year.starts_on) }} – {{ date(year.ends_on) }})</p>
        }
        @if (approvals.value(); as waiting) {
          @if (waiting.roles.length || waiting.settings.length) {
            <section class="card card-strong stack section">
              <h2 class="card-title">Waiting for your approval</h2>
              <ul class="list">
                @for (item of waiting.roles; track item.assignment_id) {
                  <li>
                    <a class="list-row" [routerLink]="['/app/staff', item.staff_id]">
                      <span class="list-main">
                        <span class="list-title">{{ item.person }}: {{ item.role_label }} · {{ item.scope_label }}</span>
                        <span class="muted small">Requested by {{ item.requested_by_name }}</span>
                      </span>
                    </a>
                  </li>
                }
                @for (item of waiting.settings; track item.revision_id) {
                  <li>
                    <a class="list-row" [routerLink]="['/app/settings', item.key]">
                      <span class="list-main">
                        <span class="list-title">{{ item.label }}: {{ item.description }}</span>
                        <span class="muted small">Sent by {{ item.submitted_by_name }}</span>
                      </span>
                    </a>
                  </li>
                }
              </ul>
            </section>
          }
        }
        @if (!roleCount()) {
          <p class="notice notice-info section" role="status">You have no role here yet. Ask your Institution Admin.</p>
        }
        <div class="grid-2 section">
          @if (auth.can('institution_profile.update')) {
            <section class="card stack">
              <h2 class="card-title">{{ institution.lifecycle_status === 'setup' ? 'Getting ready to go live' : 'Your setup' }}</h2>
              <ul class="checklist">
                @for (item of institution.readiness; track item.code) {
                  <li [class.done]="item.done">
                    <span class="mark"><app-icon [name]="item.done ? 'check' : 'minus'" [size]="14" /></span>
                    @if (!item.done && fixAt[item.code]) {
                      <a [routerLink]="fixAt[item.code]">{{ item.label }}</a>
                    } @else {
                      <span>{{ item.label }}</span>
                    }
                    <span class="sr-only">{{ item.done ? '(done)' : '(not done yet)' }}</span>
                  </li>
                }
              </ul>
              @if (institution.lifecycle_status === 'setup' && allDone()) {
                <p class="notice notice-info">Everything is ready. Activation is done by the Eduma team.</p>
              }
            </section>
          }
          <section class="card stack">
            <h2 class="card-title">Your web address</h2>
            <p class="muted small">Share it with parents, students and staff. Your team signs in from its Sign in button.</p>
            <app-copy-url [url]="institution.url" open />
            @if (auth.can('institution_brand.update')) {
              <a class="btn btn-primary" routerLink="/app/site"><app-icon name="globe" [size]="18" /> Edit your public page</a>
            }
          </section>
          <section class="card stack">
            <h2 class="card-title">Modules in your plan</h2>
            @if (institution.modules.length) {
              <p class="muted small">None is open yet: each arrives in a later release. Switched-on modules are marked.</p>
              <ul class="chips modules">
                @for (key of institution.modules; track key) {
                  <li class="chip module" [class.on]="enabled().includes(key)">
                    @if (enabled().includes(key)) { <app-icon name="check" [size]="14" /><span class="sr-only">Switched on: </span> }
                    {{ moduleLabels[key] ?? key }}
                  </li>
                }
              </ul>
            } @else {
              <p class="muted">Your plan has no modules yet. The Eduma team sets them.</p>
            }
          </section>
        </div>
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .btn {
      align-self: flex-start;
    }

    .module.on {
      border-color: var(--success);
      color: var(--success);
      gap: 6px;
    }

    .modules {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
  `,
})
export class HomePage {
  private readonly api = inject(Api);
  protected readonly auth = inject(AuthStore);
  protected readonly fixAt = FIX_AT;
  protected readonly data = load(() => this.api.get<InstitutionDetail>('institution'));
  protected readonly moduleLabels = MODULE_LABELS;
  protected readonly date = date;
  protected readonly approvals = load(() => this.api.get<Approvals>('institution/approvals'));
  protected readonly enabled = computed(() => this.data.value()?.modules_enabled ?? []);
  protected readonly roleCount = computed(() => this.auth.user()?.membership?.roles.length ?? 0);
  protected readonly allDone = computed(() => this.data.value()?.readiness.every((item) => item.done) ?? false);
}
