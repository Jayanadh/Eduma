import { NgTemplateOutlet } from '@angular/common';
import { Component, inject, input, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { ClassSessionT, MediaToken } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';
import { PortalFrame } from '../apply/portal-frame';

type Joined = { admission: string; token: MediaToken | null; session: ClassSessionT };

/** A teacher-led class (S9-07..09). The teacher starts it, lets students in or removes them, and ends it; without the
 * teacher it pauses and then closes. Recording is off. */
@Component({
  selector: 'app-class-page',
  imports: [LoadError, NgTemplateOutlet, PageHeader, PortalFrame],
  template: `
    <ng-template #body>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as s) {
        <p class="small section">{{ s.target.label }} · {{ dateTime(s.starts_at) }} · <strong>{{ s.state_label }}</strong> · hosted by {{ s.host }} · recording off</p>
        @if (status(); as m) { <p class="notice notice-info section">{{ m }}</p> }
        <div class="actions section">
          @if (s.state !== 'ended') {
            <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="join()">{{ s.is_host ? (s.state === 'live' ? 'Rejoin' : 'Start / rejoin') : 'Join' }}</button>
            <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="leave()">Leave</button>
            @if (s.is_host) { <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="act('end')">End for everyone</button> }
          }
        </div>
        @if (s.is_host) {
          <section class="card stack section">
            <h2 class="card-title">People</h2>
            <ul class="rows">
              @for (p of s.participants ?? []; track p.id) {
                <li>
                  <span>{{ p.full_name }} <span class="muted small meta">{{ p.role }} · {{ p.admission }}{{ p.present ? ' · here now' : '' }} · {{ minutes(p.seconds) }}</span></span>
                  @if (p.role !== 'host') {
                    <span class="actions">
                      @if (p.admission === 'waiting') { <button type="button" class="btn btn-primary btn-sm" [attr.aria-label]="'Let ' + p.full_name + ' in'" (click)="act('participants/' + p.id + '/admit')">Let in</button> }
                      @if (p.admission !== 'removed') { <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Remove ' + p.full_name" (click)="act('participants/' + p.id + '/remove')">Remove</button> }
                    </span>
                  }
                </li>
              } @empty {
                <li class="muted small">Nobody has joined yet.</li>
              }
            </ul>
            <p class="muted small">Time in the class is evidence only; the register stays the teacher's.</p>
          </section>
        }
      }
    </ng-template>
    @if (portal()) {
      <app-portal-frame [heading]="data.value()?.title ?? 'Class'"><ng-container [ngTemplateOutlet]="body" /></app-portal-frame>
    } @else {
      <div class="page"><app-page-header eyebrow="Online class" [title]="data.value()?.title ?? 'Class'" backLink="/app/teaching" /><ng-container [ngTemplateOutlet]="body" /></div>
    }
  `,
  styles: `
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

  `,
})
export class ClassPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly portal = signal(!!inject(ActivatedRoute).snapshot.data['portal']);
  protected readonly dateTime = dateTime;
  protected readonly data = load(
    () => this.api.get<ClassSessionT>(`communication/classes/${this.id()}`),
    () => this.id(),
  );
  protected readonly status = signal('');
  protected readonly busy = signal(false);

  protected minutes(seconds: number): string {
    return `${Math.round(seconds / 60)} min`;
  }

  private run<T>(request: Observable<T>, after: (result: T) => void): void {
    this.busy.set(true);
    request.subscribe({
      next: (result) => {
        this.busy.set(false);
        after(result);
      },
      error: (err) => {
        this.busy.set(false);
        this.status.set(apiErrorMessage(err));
        this.data.reload();
      },
    });
  }

  protected join(): void {
    this.run(this.api.post<Joined>(`communication/classes/${this.id()}/join`, {}), (joined) => {
      this.data.value.set(joined.session);
      this.status.set(
        joined.admission === 'waiting'
          ? 'Waiting for the teacher to let you in.'
          : `You're in (test mode: no audio or video provider is attached yet; your ${joined.token?.role} token lasts ${Math.round((joined.token?.expires_in ?? 0) / 60)} minutes).`,
      );
    });
  }

  protected leave(): void {
    this.run(this.api.post<ClassSessionT>(`communication/classes/${this.id()}/leave`, {}), (s) => {
      this.data.value.set(s);
      this.status.set('You left.');
    });
  }

  protected act(path: string): void {
    this.run(this.api.post<ClassSessionT>(`communication/classes/${this.id()}/${path}`, {}), (s) => {
      this.data.value.set(s);
      this.toasts.show('Done.');
    });
  }
}
