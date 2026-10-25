import { NgTemplateOutlet } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { ConversationT, FamilyChild, NotificationT } from '../../core/api/types';
import { AuthStore } from '../../core/auth-store';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from '../apply/portal-frame';

/** Conversations and notifications (S9-02..05). Staff see it in the workspace, guardians in the family portal; who
 * can be reached is decided by the server from today's relationships. */
@Component({
  selector: 'app-messages-page',
  imports: [LoadError, NgTemplateOutlet, PageHeader, PortalFrame, RouterLink],
  template: `
    <ng-template #body>
      <app-load-error [message]="list.error()" (retry)="list.reload()" />
      @if (notices.value()?.length) {
        <section class="card stack section">
          <h2 class="card-title">Notifications</h2>
          <ul class="bullets">@for (n of notices.value() ?? []; track n.id) { <li><a [routerLink]="route(n.link)">{{ n.text }}</a><span class="muted small meta">{{ dateTime(n.at) }}</span></li> }</ul>
        </section>
      }
      <div class="card list-card section">
        <ul class="list">
          @for (c of list.value() ?? []; track c.id) {
            <li><a class="list-row" [routerLink]="[base(), c.id]">
              <span class="list-main"><span class="list-title">{{ c.subject }}</span>
                <span class="muted small">{{ c.student ? c.student.full_name + ' · ' : '' }}{{ names(c) }}</span></span>
              @if (c.unread) { <span class="badge badge-info">{{ c.unread }} new</span> }
            </a></li>
          } @empty {
            <li class="list-row muted small">No conversations yet.</li>
          }
        </ul>
      </div>
      <form id="new-conversation" class="card stack section" (submit)="$event.preventDefault(); start($any($event.target))">
        <h2 class="card-title">New conversation</h2>
        @if (portal()) {
          <div class="field"><label for="new-child">About</label>
            <select id="new-child" (change)="student.set($any($event.target).value)">
              <option value="">Choose a child</option>
              @for (c of children.value() ?? []; track c.id) { <option [value]="c.id">{{ c.full_name }}</option> }
            </select></div>
        } @else {
          <div class="field"><label for="new-student-number">About a student (number, or leave empty for staff)</label>
            <input id="new-student-number" placeholder="2026-0001" (change)="find($any($event.target).value)" /></div>
        }
        <div class="field"><label for="new-to">With</label>
          <select id="new-to">@for (p of contacts.value() ?? []; track p.id) { <option [value]="p.id">{{ p.full_name }}</option> } @empty { <option value="">Nobody you can write to</option> }</select></div>
        <div class="field"><label for="new-subject">Subject</label><input id="new-subject" /></div>
        <div class="field"><label for="new-body">Message</label><textarea id="new-body" rows="3"></textarea></div>
        <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Send</button></div>
      </form>
    </ng-template>
    @if (portal()) {
      <app-portal-frame heading="Messages"><ng-container [ngTemplateOutlet]="body" /></app-portal-frame>
    } @else {
      <div class="page">
        <app-page-header eyebrow="Communication" title="Messages" subtitle="Teachers and families of the students they teach, and staff with each other." />
        <ng-container [ngTemplateOutlet]="body" />
      </div>
    }
  `,
  styles: `
    .bullets {
      margin: 0;
      padding-left: 18px;
    }
  `,
})
export class MessagesPage {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  private readonly auth = inject(AuthStore);
  protected readonly portal = signal(!!inject(ActivatedRoute).snapshot.data['portal']);
  protected readonly base = computed(() => (this.portal() ? '/family/messages' : '/app/messages'));
  protected readonly dateTime = dateTime;
  protected readonly list = load(() => this.api.get<ConversationT[]>('communication/conversations'));
  protected readonly notices = load(() => this.api.get<NotificationT[]>('communication/notifications'));
  protected readonly children = load(() => (this.portal() ? this.api.get<FamilyChild[]>('family/children') : of([] as FamilyChild[])));
  protected readonly student = signal('');
  protected readonly contacts = load(
    () => this.api.get<{ id: string; full_name: string }[]>('communication/contacts', this.student() ? { student: this.student() } : {}),
    () => this.student(),
  );
  protected readonly busy = signal(false);

  /** Notification links are /messages/<id> or /calls/<id>; they open here in the workspace or the family portal. */
  protected route(link: string): string {
    const [, kind, id] = link.split('/');
    const root = this.portal() ? '/family' : '/app';
    return kind === 'calls' ? `${root}/calls/${id}` : `${root}/messages/${id}`;
  }

  protected names(c: ConversationT): string {
    return c.others.map((o) => o.full_name).join(', ');
  }

  /** Staff type a student number; the student's id comes from the directory search. */
  protected find(number: string): void {
    if (!number.trim()) {
      this.student.set('');
      return;
    }
    this.api.get<{ results: { id: string; number: string }[] }>('institution/students', { search: number.trim() }).subscribe({
      next: (found) => this.student.set(found.results.find((s) => s.number === number.trim())?.id ?? ''),
      error: () => this.student.set(''),
    });
  }

  protected start(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(`#${id}`)!.value.trim();
    const body = {
      student: this.student() || null,
      with: field('new-to'),
      subject: field('new-subject'),
      body: field('new-body'),
      client_id: crypto.randomUUID(),
    };
    this.busy.set(true);
    this.api.post<ConversationT>('communication/conversations', body).subscribe({
      next: (made) => {
        this.busy.set(false);
        this.router.navigate([this.base(), made.id]);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected can(perm: string): boolean {
    return this.auth.can(perm);
  }
}
