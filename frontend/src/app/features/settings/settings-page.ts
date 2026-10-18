import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { SettingSummary } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { Icon } from '../../ui/icon';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';

/** The institution's settings: what is in force, what is scheduled, and what is being changed. */
@Component({
  selector: 'app-settings-page',
  imports: [Icon, LoadError, PageHeader, RouterLink],
  template: `
    <div class="page">
      <app-page-header title="Settings" subtitle="Changes are drafted, checked and published from a day you choose. Earlier values stay in the history." />
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as settings) {
        <div class="stack section">
          @for (item of settings; track item.key) {
            <article class="card stack">
              <div class="head">
                <h2 class="card-title">{{ item.label }}</h2>
                @if (item.open?.status === 'pending') {
                  <span class="badge badge-warning">Waiting for approval</span>
                } @else if (item.open?.status === 'draft') {
                  <span class="badge badge-info">Draft</span>
                }
              </div>
              <p class="muted small">{{ item.help }}</p>
              <p><strong>Now:</strong> {{ item.description_now }}</p>
              @if (item.scheduled; as next) {
                <p class="small">From {{ date(next.effective_from) }}: {{ next.description }}</p>
              }
              <a class="btn btn-secondary btn-sm change" [routerLink]="['/app/settings', item.key]">
                <app-icon name="pencil" [size]="16" /> {{ item.open ? 'Continue' : 'Change' }}
              </a>
            </article>
          }
        </div>
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .head {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 12px;
    }

    .change {
      align-self: flex-start;
    }
  `,
})
export class SettingsPage {
  private readonly api = inject(Api);
  protected readonly date = date;
  protected readonly data = load(() => this.api.get<SettingSummary[]>('institution/settings'));
}
