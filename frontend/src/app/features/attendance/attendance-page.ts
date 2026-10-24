import { Component, inject, input, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { AttendanceCode, AttendanceSessionT } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

const CODES: [AttendanceCode, string][] = [
  ['present', 'Present'],
  ['late', 'Late'],
  ['absent', 'Absent'],
  ['excused', 'Excused'],
];

/** Taking a register (S6-06): mark, save, submit. Once submitted, a change is a correction someone else approves. */
@Component({
  selector: 'app-attendance-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as s) {
        <app-page-header eyebrow="Attendance" [title]="s.target.label + ' · ' + date(s.date)" [subtitle]="s.state_label + (s.unmarked ? ' · ' + s.unmarked + ' not marked' : '')" backLink="/app/teaching">
          @if (s.state === 'draft') {
            <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="allPresent(s)">Everyone present</button>
            <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="save(s, true)">Submit</button>
          }
        </app-page-header>
        <div class="card list-card section">
          <ul class="list">
            @for (r of s.roster; track r.student.id) {
              <li class="list-row row">
                <span class="list-main"><span class="list-title">{{ r.student.number }} · {{ r.student.full_name }}</span></span>
                @if (s.state === 'draft') {
                  <span class="codes" role="radiogroup" [attr.aria-label]="'Attendance for ' + r.student.full_name">
                    @for (c of codes; track c[0]) {
                      <label class="code" [class.on]="(picked()[r.student.id] ?? r.code) === c[0]">
                        <input type="radio" [name]="'code-' + r.student.id" [id]="'code-' + r.student.id + '-' + c[0]" [checked]="(picked()[r.student.id] ?? r.code) === c[0]" (change)="pick(r.student.id, c[0])" />
                        {{ c[1] }}
                      </label>
                    }
                  </span>
                } @else {
                  <span class="small">{{ label(r.code) }}</span>
                  @if (r.mark && correcting() !== r.mark) {
                    <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Correct ' + r.student.full_name" [disabled]="busy()" (click)="correcting.set(r.mark)">Correct</button>
                  }
                  @if (r.mark && correcting() === r.mark) {
                    <form class="fix" [id]="'fix-' + r.mark" (submit)="$event.preventDefault(); correct(r.mark, $any($event.target))">
                      <label class="sr-only" [for]="'fix-code-' + r.mark">New mark</label>
                      <select [id]="'fix-code-' + r.mark">
                        @for (c of codes; track c[0]) { @if (c[0] !== r.code) { <option [value]="c[0]">{{ c[1] }}</option> } }
                      </select>
                      <label class="sr-only" [for]="'fix-reason-' + r.mark">Why</label>
                      <input [id]="'fix-reason-' + r.mark" placeholder="Why" required />
                      <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Ask for approval</button>
                    </form>
                  }
                }
              </li>
            } @empty {
              <li class="list-row muted small">Nobody is on this register that day.</li>
            }
          </ul>
        </div>
        @if (s.state === 'draft') {
          <div class="section"><button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="save(s, false)">Save without submitting</button></div>
        }
      }
    </div>
  `,
  styles: `
    .row {
      flex-wrap: wrap;
    }

    .codes {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .fix {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .code {
      padding: 4px 10px;
      border: 1px solid var(--border);
      border-radius: 999px;
      cursor: pointer;

      &.on {
        border-color: var(--primary);
        font-weight: 600;
      }

      input {
        position: absolute;
        opacity: 0;
      }
    }
  `,
})
export class AttendancePage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly codes = CODES;
  protected readonly data = load(
    () => this.api.get<AttendanceSessionT>(`teaching/attendance/${this.id()}`),
    () => this.id(),
  );
  /** Marks chosen on this page and not yet saved. */
  protected readonly picked = signal<Record<string, AttendanceCode>>({});
  protected readonly busy = signal(false);
  protected readonly correcting = signal<string | null>(null);

  protected label(code: string | null): string {
    return CODES.find((c) => c[0] === code)?.[1] ?? 'Not marked';
  }

  protected pick(student: string, code: AttendanceCode): void {
    this.picked.update((all) => ({ ...all, [student]: code }));
  }

  protected allPresent(s: AttendanceSessionT): void {
    this.picked.set(Object.fromEntries(s.roster.map((r) => [r.student.id, 'present' as AttendanceCode])));
  }

  protected save(s: AttendanceSessionT, andSubmit: boolean): void {
    const marks = Object.entries(this.picked()).map(([student, code]) => ({ student, code }));
    this.busy.set(true);
    this.api.post<AttendanceSessionT>(`teaching/attendance/${s.id}/marks`, { version: s.version, marks }).subscribe({
      next: (saved) => {
        this.picked.set({});
        if (!andSubmit) {
          this.busy.set(false);
          this.data.value.set(saved);
          this.toasts.show('Saved. Not submitted yet.');
          return;
        }
        this.api.post<AttendanceSessionT>(`teaching/attendance/${s.id}/submit`, { version: saved.version }).subscribe({
          next: (sent) => {
            this.busy.set(false);
            this.data.value.set(sent);
            this.toasts.show('Attendance submitted.');
          },
          error: (err) => this.fail(err),
        });
      },
      error: (err) => this.fail(err),
    });
  }

  private fail(err: unknown): void {
    this.busy.set(false);
    this.toasts.show(apiErrorMessage(err), 'danger');
    this.data.reload();
  }

  protected correct(mark: string, form: HTMLFormElement): void {
    const code = form.querySelector<HTMLSelectElement>(`#fix-code-${mark}`)!.value;
    const reason = form.querySelector<HTMLInputElement>(`#fix-reason-${mark}`)!.value.trim();
    if (!reason) {
      return;
    }
    this.busy.set(true);
    this.api.post(`teaching/attendance/marks/${mark}/corrections`, { code, reason }).subscribe({
      next: () => {
        this.busy.set(false);
        this.correcting.set(null);
        this.toasts.show('Correction sent for approval; the original mark is kept.');
      },
      error: (err) => this.fail(err),
    });
  }
}
