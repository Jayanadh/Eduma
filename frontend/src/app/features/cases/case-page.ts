import { NgTemplateOutlet } from '@angular/common';
import { Component, inject, input, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Observable, of } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from '../apply/portal-frame';
import { CaseT } from './case-types';

/** One case, as the person looking may see it (S10C-02): notes, assignment, resolution and appeal. */
@Component({
  selector: 'app-case-page',
  imports: [LoadError, NgTemplateOutlet, PageHeader, PortalFrame],
  template: `
    <ng-template #body>
      <app-load-error [message]="item.error()" (retry)="item.reload()" />
      @if (item.value(); as c) {
        <section class="card stack section">
          <p class="small">{{ c.type_label }} · {{ c.state_label }} · opened {{ dateTime(c.created_at) }}{{ c.requester ? ' by ' + c.requester : '' }}{{ c.assignee ? ' · with ' + c.assignee : '' }}{{ c.due_at ? ' · due ' + dateTime(c.due_at) : '' }}</p>
          @if (c.subject) {
            <h2 class="card-title">{{ c.subject }}</h2>
            <p class="pre">{{ c.description }}</p>
          } @else {
            <p class="muted small">A confidential case: only the officer it is assigned to sees what it is about.</p>
          }
        </section>
        @for (r of c.resolutions ?? []; track r.at) {
          <section class="card stack section">
            <h2 class="card-title">{{ r.stage === 'appeal' ? 'Appeal decision' : 'Resolution' }}</h2>
            <p class="pre">{{ r.text }}</p>
            <p class="muted small">{{ dateTime(r.at) }}</p>
          </section>
        }
        @if (c.appeal; as a) {
          <section class="card stack section"><h2 class="card-title">Appeal</h2><p class="pre">{{ a.reason }}</p></section>
        }
        @if (c.notes) {
          <section class="card stack section">
            <h2 class="card-title">Notes</h2>
            <ul class="notes">
              @for (n of c.notes; track n.at) {
                <li [class.internal]="n.visibility === 'internal'"><p class="pre">{{ n.text }}</p><span class="muted small">{{ n.by }} · {{ dateTime(n.at) }}{{ n.visibility === 'internal' ? ' · internal' : '' }}</span></li>
              } @empty {
                <li class="muted small">No notes yet.</li>
              }
            </ul>
            @if (c.state !== 'resolved') {
              <form id="note" class="stack" (submit)="$event.preventDefault(); note($any($event.target))">
                <div class="field"><label for="note-text">{{ c.seen_as === 'officer' ? 'Note' : 'Reply' }}</label><textarea id="note-text" rows="3" maxlength="4000" required></textarea></div>
                @if (c.seen_as === 'officer') {
                  <label><input id="note-internal" type="checkbox" /> Internal: never shown to the requester</label>
                }
                <div><button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add</button></div>
              </form>
            }
          </section>
        }
        @if (c.seen_as === 'triage' && c.state !== 'resolved') {
          <section class="card stack section">
            <h2 class="card-title">{{ c.assignee ? 'Reassign' : 'Assign' }}</h2>
            <div class="field"><label for="assignee">Handled by</label>
              <select id="assignee">@for (o of officers.value() ?? []; track o.id) { <option [value]="o.id">{{ o.name }}</option> } @empty { <option value="">Nobody can take this case</option> }</select></div>
            <div><button type="button" id="assign" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="assign()">Assign</button></div>
          </section>
        }
        @if (c.seen_as === 'officer' && c.state === 'assigned') {
          <form id="resolve" class="card stack section" (submit)="$event.preventDefault(); resolve($any($event.target))">
            <h2 class="card-title">Resolve</h2>
            <div class="field"><label for="resolution">What was decided (the requester sees this)</label><textarea id="resolution" rows="3" required></textarea></div>
            <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Resolve</button></div>
          </form>
        }
        @if (c.can_appeal) {
          <form id="appeal" class="card stack section" (submit)="$event.preventDefault(); appeal($any($event.target))">
            <h2 class="card-title">Appeal</h2>
            <p class="muted small">Once, within 15 days. Someone else reviews it; the first decision stays on record.</p>
            <div class="field"><label for="appeal-reason">Why</label><textarea id="appeal-reason" rows="3" required></textarea></div>
            <div><button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Appeal</button></div>
          </form>
        }
      }
    </ng-template>
    @if (portal()) {
      <app-portal-frame [heading]="item.value()?.number ?? 'Case'"><ng-container [ngTemplateOutlet]="body" /></app-portal-frame>
    } @else {
      <div class="page">
        <app-page-header eyebrow="Cases" [title]="item.value()?.number ?? 'Case'" />
        <ng-container [ngTemplateOutlet]="body" />
      </div>
    }
  `,
  styles: `
    .pre {
      white-space: pre-wrap;
    }

    .notes {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .internal {
      padding-left: 10px;
      border-left: 3px solid var(--border);
    }
  `,
})
export class CasePage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  readonly id = input.required<string>();
  protected readonly dateTime = dateTime;
  protected readonly portal = signal(!!inject(ActivatedRoute).snapshot.data['portal']);
  protected readonly item = load(() => this.api.get<CaseT>(`service-cases/${this.id()}`), () => this.id());
  protected readonly officers = load(
    () => (this.item.value()?.seen_as === 'triage' ? this.api.get<{ id: string; name: string }[]>(`service-cases/${this.id()}/officers`) : of([])),
    () => this.item.value()?.seen_as,
  );
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        this.item.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected note(form: HTMLFormElement): void {
    const text = form.querySelector<HTMLTextAreaElement>('#note-text')!.value;
    const internal = form.querySelector<HTMLInputElement>('#note-internal')?.checked ?? false;
    this.run(this.api.post(`service-cases/${this.id()}/notes`, { text, visibility: internal ? 'internal' : 'requester_visible' }), 'Added.', () => form.reset());
  }

  protected assign(): void {
    const assignee = (document.getElementById('assignee') as HTMLSelectElement | null)?.value;
    this.run(this.api.post(`service-cases/${this.id()}/assign`, { assignee }), 'Assigned.');
  }

  protected resolve(form: HTMLFormElement): void {
    this.run(this.api.post(`service-cases/${this.id()}/resolve`, { text: form.querySelector<HTMLTextAreaElement>('#resolution')!.value }), 'Resolved.');
  }

  protected appeal(form: HTMLFormElement): void {
    this.run(this.api.post(`service-cases/${this.id()}/appeals`, { reason: form.querySelector<HTMLTextAreaElement>('#appeal-reason')!.value }), 'Appeal sent.');
  }
}
