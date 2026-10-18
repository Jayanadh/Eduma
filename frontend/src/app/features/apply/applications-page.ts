import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { ApplicantApplication, Page, PublicAdmissions } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { Pager } from '../../ui/pager';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from './portal-frame';

/** An applicant's applications, and starting a new one for an open cycle's place. */
@Component({
  selector: 'app-applications-page',
  imports: [EmptyState, LoadError, Pager, PortalFrame, RouterLink],
  template: `
    <app-portal-frame heading="Your applications">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as result) {
        @if (result.results.length) {
          <div class="card list-card">
            <ul class="list">
              @for (item of result.results; track item.id) {
                <li>
                  <a class="list-row" [routerLink]="['/apply/applications', item.id]">
                    <span class="list-main">
                      <span class="list-title">{{ item.learner_name || 'New application' }} · {{ item.place.label }}</span>
                      <span class="muted small">{{ item.cycle.name }}{{ item.number ? ' · ' + item.number : '' }}</span>
                    </span>
                    <span class="badge badge-info">{{ item.stage_label }}</span>
                  </a>
                </li>
              }
            </ul>
          </div>
          <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
        } @else {
          <app-empty-state icon="file-plus" title="No applications yet" text="Choose a place below to start one." />
        }
      }
      @if (admissions.value(); as open) {
        @if (open.cycles.length) {
          <section class="card stack">
            <h2 class="card-title">Start an application</h2>
            @for (cycle of open.cycles; track cycle.id) {
              <p class="muted small">{{ cycle.name }} · closes {{ date(cycle.closes_on) }}</p>
              <div class="places">
                @for (place of cycle.places; track place.id) {
                  <button type="button" class="btn btn-secondary" [disabled]="busy()" (click)="start(cycle.id, place.id)">
                    {{ place.label }}{{ place.campus_name ? ' · ' + place.campus_name : '' }}
                  </button>
                }
              </div>
            }
          </section>
        } @else {
          <p class="notice notice-info">Admissions are not open right now.</p>
        }
      }
    </app-portal-frame>
  `,
  styles: `
    .places {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
  `,
})
export class ApplicationsPage {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly page = signal(1);
  protected readonly busy = signal(false);
  protected readonly data = load(
    () => this.api.get<Page<ApplicantApplication>>('applicant/applications', { page: this.page() }),
    () => this.page(),
  );
  protected readonly admissions = load(() => this.api.get<PublicAdmissions>('public/admissions'));

  protected start(cycle: string, place: string): void {
    this.busy.set(true);
    this.api.post<ApplicantApplication>('applicant/applications', { cycle, place }).subscribe({
      next: (created) => void this.router.navigate(['/apply/applications', created.id]),
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
