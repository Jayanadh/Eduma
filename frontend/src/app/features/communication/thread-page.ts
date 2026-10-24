import { NgTemplateOutlet } from '@angular/common';
import { Component, effect, inject, input, signal, untracked } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { CallT, ConversationT } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from '../apply/portal-frame';

/** One conversation: messages in order, a reply that is safe to retry, and a call to the other person. */
@Component({
  selector: 'app-thread-page',
  imports: [LoadError, NgTemplateOutlet, PageHeader, PortalFrame],
  template: `
    <ng-template #body>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as c) {
        <p class="muted small section">{{ c.student ? 'About ' + c.student.full_name + ' · ' : '' }}with {{ others(c) }}</p>
        <ol class="messages section">
          @for (m of c.messages ?? []; track m.sequence) {
            <li [class.mine]="m.mine"><span class="small"><strong>{{ m.sender }}</strong> <span class="muted">{{ dateTime(m.at) }}</span></span><p>{{ m.body }}</p></li>
          }
        </ol>
        <form id="reply" class="stack section" (submit)="$event.preventDefault(); reply(c, $any($event.target))">
          <label for="reply-body" class="sr-only">Reply</label>
          <textarea id="reply-body" rows="3" placeholder="Write a reply"></textarea>
          <div class="actions">
            <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Send</button>
            @if (c.others.length === 1) { <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="call(c)">Call {{ c.others[0].full_name }}</button> }
          </div>
        </form>
        @if (current(); as k) {
          <section class="card stack section">
            <p class="small">Call: <strong>{{ k.state_label }}</strong>{{ k.reason === 'integration_not_configured' ? ' — no call provider is set up here' : '' }}</p>
            @if (k.token) { <p class="muted small">Test mode: the call is connected in Eduma, but no audio provider is attached yet.</p> }
            @if (k.state === 'ringing' || k.state === 'connected') { <button type="button" class="btn btn-secondary btn-sm" (click)="hangUp(k)">{{ k.state === 'ringing' ? 'Cancel' : 'End call' }}</button> }
          </section>
        }
      }
    </ng-template>
    @if (portal()) {
      <app-portal-frame [heading]="data.value()?.subject ?? 'Conversation'"><ng-container [ngTemplateOutlet]="body" /></app-portal-frame>
    } @else {
      <div class="page">
        <app-page-header eyebrow="Messages" [title]="data.value()?.subject ?? 'Conversation'" backLink="/app/messages" />
        <ng-container [ngTemplateOutlet]="body" />
      </div>
    }
  `,
  styles: `
    .messages {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;

      li {
        max-width: 80%;
        padding: 8px 12px;
        border-radius: 12px;
        background: var(--surface);
        border: 1px solid var(--border);
      }

      li.mine {
        align-self: flex-end;
      }

      p {
        margin: 4px 0 0;
        white-space: pre-wrap;
      }
    }

    .actions {
      display: flex;
      gap: 8px;
    }
  `,
})
export class ThreadPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly portal = signal(!!inject(ActivatedRoute).snapshot.data['portal']);
  protected readonly dateTime = dateTime;
  protected readonly data = load(
    () => this.api.get<ConversationT>(`communication/conversations/${this.id()}`),
    () => this.id(),
  );
  protected readonly current = signal<CallT | null>(null);
  protected readonly busy = signal(false);
  /** One id per message being written: a retried send can't post it twice. */
  private draftId = crypto.randomUUID();

  constructor() {
    effect(() => {
      const c = this.data.value();
      if (c?.last_sequence) {
        untracked(() => this.api.post(`communication/conversations/${c.id}/read`, { sequence: c.last_sequence }).subscribe({ error: () => undefined }));
      }
    });
  }

  protected others(c: ConversationT): string {
    return c.others.map((o) => o.full_name).join(', ');
  }

  protected reply(c: ConversationT, form: HTMLFormElement): void {
    const text = form.querySelector<HTMLTextAreaElement>('#reply-body')!.value.trim();
    if (!text) {
      return;
    }
    this.busy.set(true);
    this.api.post(`communication/conversations/${c.id}/messages`, { body: text, client_id: this.draftId }).subscribe({
      next: () => {
        this.busy.set(false);
        this.draftId = crypto.randomUUID();
        form.reset();
        this.data.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected call(c: ConversationT): void {
    this.api.post<CallT>('communication/calls', { conversation: c.id }).subscribe({
      next: (k) => this.current.set(k),
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }

  protected hangUp(k: CallT): void {
    this.api.post<CallT>(`communication/calls/${k.id}/${k.state === 'ringing' ? 'cancel' : 'end'}`, {}).subscribe({
      next: (done) => this.current.set(done),
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }
}
