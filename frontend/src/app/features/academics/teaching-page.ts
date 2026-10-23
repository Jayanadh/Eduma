import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { TeachingClass } from '../../core/api/types';
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
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as classes) {
        @if (classes.length) {
          <div class="card list-card section">
            <ul class="list">
              @for (c of classes; track c.section.id) {
                <li>
                  <a class="list-row" [routerLink]="['/app/teaching', c.section.id]">
                    <span class="list-main">
                      <span class="list-title">{{ c.section.code }} · {{ c.section.grade }} · {{ c.section.year }}</span>
                      <span class="muted small">{{ c.subjects.length ? c.subjects.join(', ') : 'The whole class' }}</span>
                    </span>
                    @if (c.class_teacher) { <span class="badge badge-info">Class teacher</span> }
                  </a>
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
})
export class TeachingPage {
  private readonly api = inject(Api);
  protected readonly data = load(() => this.api.get<TeachingClass[]>('teaching/classes'));
}
