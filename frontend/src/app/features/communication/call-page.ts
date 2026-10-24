import { NgTemplateOutlet } from '@angular/common';
import { Component, inject, input, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { CallT } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from '../apply/portal-frame';

/** An incoming or ongoing call (S9-06): answer or decline while it rings; it can't be reopened once over. */
@Component({
  selector: 'app-call-page',
  imports: [LoadError, NgTemplateOutlet, PageHeader, PortalFrame],
  template: `
    <ng-template #body>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as k) {
        <section class="card stack section">
          <p>{{ k.caller }} → {{ k.callee }}: <strong>{{ k.state_label }}</strong>{{ k.reason === 'integration_not_configured' ? ' — no call provider is set up here' : '' }}</p>
          @if (k.token) { <p class="muted small">Test mode: connected in Eduma; no audio provider is attached yet.</p> }
          <div class="actions">
            @if (k.state === 'ringing') {
              <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="act(k, 'accept')">Answer</button>
              <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="act(k, 'decline')">Decline</button>
            }
            @if (k.state === 'connected') { <button type="button" class="btn btn-secondary btn-sm" (click)="act(k, 'end')">End call</button> }
          </div>
        </section>
      }
    </ng-template>
    @if (portal()) {
      <app-portal-frame heading="Call"><ng-container [ngTemplateOutlet]="body" /></app-portal-frame>
    } @else {
      <div class="page"><app-page-header eyebrow="Communication" title="Call" backLink="/app/messages" /><ng-container [ngTemplateOutlet]="body" /></div>
    }
  `,
  styles: `
    .actions {
      display: flex;
      gap: 8px;
    }
  `,
})
export class CallPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly portal = signal(!!inject(ActivatedRoute).snapshot.data['portal']);
  protected readonly data = load(
    () => this.api.get<CallT>(`communication/calls/${this.id()}`),
    () => this.id(),
  );
  protected readonly busy = signal(false);

  protected act(k: CallT, action: 'accept' | 'decline' | 'end'): void {
    this.busy.set(true);
    this.api.post<CallT>(`communication/calls/${k.id}/${action}`, {}).subscribe({
      next: (done) => {
        this.busy.set(false);
        this.data.value.set(done);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
        this.data.reload();
      },
    });
  }
}
