import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/api-error';
import { ToastService } from '../../ui/toast';
import { Api } from '../../core/api/api';
import { AttendanceSessionT, Lesson, TeachingClass } from '../../core/api/types';
import { load } from '../../core/load';
import { EmptyState } from '../../ui/empty-state';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';

/** The classes a teacher teaches (SCR-023, the roster part). Attendance and lessons join this page later. */
@Component({
  selector: 'app-teaching-page',
  imports: [EmptyState, LoadError, PageHeader, RouterLink],
  template: `
    <div class="page">
      <app-page-header eyebrow="Teaching" title="My classes" />
      <section class="card stack section">
        <div class="day-head">
          <h2 class="card-title">Lessons</h2>
          <label class="sr-only" for="day-date">Day</label>
          <input id="day-date" type="date" [value]="day()" (change)="day.set($any($event.target).value)" />
        </div>
        <ul class="lessons">
          @for (l of lessons.value() ?? []; track l.id) {
            <li>
              <span><strong>{{ l.starts_at }}–{{ l.ends_at }}</strong> {{ l.target.label }}{{ l.subject ? ' · ' + l.subject : '' }}{{ l.room ? ' · ' + l.room.code : '' }}{{ l.substitute ? ' · covering' : '' }}</span>
              <button type="button" class="btn btn-sm" [class.btn-primary]="!l.session" [class.btn-secondary]="!!l.session" [disabled]="busy()" (click)="register(l)">
                {{ l.session ? (l.session.state === 'draft' ? 'Continue register' : 'Open register') : 'Take attendance' }}
              </button>
            </li>
          } @empty {
            <li class="muted small">No timetabled lessons that day.</li>
          }
        </ul>
      </section>
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as classes) {
        @if (classes.length) {
          <div class="card list-card section">
            <ul class="list">
              @for (c of classes; track c.section?.id ?? c.offering?.id) {
                <li>
                  @if (c.section; as s) {
                    <a class="list-row" [routerLink]="['/app/teaching', s.id]">
                      <span class="list-main">
                        <span class="list-title">{{ s.code }} · {{ s.grade }} · {{ s.year }}</span>
                        <span class="muted small">{{ c.subjects.length ? c.subjects.join(', ') : 'The whole class' }}</span>
                      </span>
                      @if (c.class_teacher) { <span class="badge badge-info">Class teacher</span> }
                    </a>
                  } @else if (c.offering; as o) {
                    <a class="list-row" [routerLink]="['/app/teaching/offerings', o.id]">
                      <span class="list-main">
                        <span class="list-title">{{ o.course }}-{{ o.code }} · {{ o.title }} · {{ o.term }}</span>
                        <span class="muted small">{{ o.year }} · Course offering</span>
                      </span>
                    </a>
                  }
                </li>
              }
            </ul>
          </div>
        } @else {
          <app-empty-state icon="book" title="No classes yet" text="Classes appear here once the office assigns you to a section." />
        }
      } @else if (data.loading()) {
        <p class="muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: `
    .day-head {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }

    .lessons {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;

      li {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
    }
  `,
})
export class TeachingPage {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastService);
  protected readonly data = load(() => this.api.get<TeachingClass[]>('teaching/classes'));
  protected readonly day = signal(new Date().toLocaleDateString('en-CA'));
  protected readonly lessons = load(
    () => this.api.get<Lesson[]>('teaching/day', { date: this.day() }),
    () => this.day(),
  );
  protected readonly busy = signal(false);

  protected register(lesson: Lesson): void {
    if (lesson.session) {
      this.router.navigate(['/app/teaching/attendance', lesson.session.id]);
      return;
    }
    this.busy.set(true);
    const body = { [lesson.target.kind]: lesson.target.id, date: this.day(), slot: lesson.id };
    this.api.post<AttendanceSessionT>('teaching/attendance', body).subscribe({
      next: (session) => {
        this.busy.set(false);
        this.router.navigate(['/app/teaching/attendance', session.id]);
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }
}
