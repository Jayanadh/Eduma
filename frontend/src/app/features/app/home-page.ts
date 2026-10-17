import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { InstitutionDetail } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { load } from '../../core/load';
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
        <div class="grid-2 section">
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
          <section class="card stack">
            <h2 class="card-title">Your web address</h2>
            <p class="muted small">Share it with parents, students and staff. Your team signs in from its Sign in button.</p>
            <app-copy-url [url]="institution.url" open />
            <a class="btn btn-primary" routerLink="/app/site"><app-icon name="globe" [size]="18" /> Edit your public page</a>
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
  `,
})
export class HomePage {
  private readonly api = inject(Api);
  protected readonly auth = inject(AuthStore);
  protected readonly fixAt = FIX_AT;
  protected readonly data = load(() => this.api.get<InstitutionDetail>('institution'));
  protected readonly allDone = computed(() => this.data.value()?.readiness.every((item) => item.done) ?? false);
}
