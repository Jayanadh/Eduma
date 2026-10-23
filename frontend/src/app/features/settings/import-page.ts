import { Component, computed, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { ImportJob, ImportRow, Page } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';
import { ToastService } from '../../ui/toast';

const STATES: [string, string][] = [
  ['', 'All rows'],
  ['valid', 'Ready'],
  ['duplicate', 'Possible duplicates'],
  ['error', 'With errors'],
  ['unchanged', 'Already imported'],
  ['changed', 'Changed since the last import'],
];

/** One import: the dry run's counts and rows, duplicate decisions, then import, discard or undo. */
@Component({
  selector: 'app-import-page',
  imports: [LoadError, PageHeader, Pager, RouterLink],
  templateUrl: './import-page.html',
  styles: `
    .totals {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 20px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .row-actions {
      display: flex;
      gap: 8px;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }

    .problems {
      margin: 4px 0 0;
      padding-left: 18px;
    }
  `,
})
export class ImportPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  protected readonly states = STATES;
  protected readonly dateTime = dateTime;
  protected readonly state = signal('');
  protected readonly page = signal(1);
  protected readonly busy = signal(false);
  protected readonly job = load(
    () => this.api.get<ImportJob>(`institution/imports/${this.id()}`),
    () => this.id(),
  );
  protected readonly rows = load(
    () => this.api.get<Page<ImportRow>>(`institution/imports/${this.id()}/rows`, { state: this.state(), page: this.page() }),
    () => [this.id(), this.state(), this.page()],
  );
  protected readonly importable = computed(() => {
    const job = this.job.value();
    if (!job || job.status !== 'validated' || job.undecided > 0) {
      return false;
    }
    return (job.totals['valid'] ?? 0) + (job.totals['duplicate'] ?? 0) > 0;
  });

  private failed(err: unknown): void {
    this.busy.set(false);
    this.toasts.show(apiErrorMessage(err), 'danger');
    this.job.reload();
    this.rows.reload();
  }

  protected filter(value: string): void {
    this.state.set(value);
    this.page.set(1);
  }

  protected decide(row: ImportRow, decision: 'create' | 'skip'): void {
    this.busy.set(true);
    this.api.post<ImportRow>(`institution/imports/${this.id()}/rows/${row.id}/decide`, { decision }).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.rows.value.update((page) => page && { ...page, results: page.results.map((r) => (r.id === updated.id ? updated : r)) });
        this.job.reload();
      },
      error: (err) => this.failed(err),
    });
  }

  private act(job: ImportJob, step: 'commit' | 'discard' | 'undo', message: string): void {
    this.busy.set(true);
    this.api.post<ImportJob>(`institution/imports/${job.id}/${step}`, { version: job.version }).subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(message);
        this.job.reload();
        this.rows.reload();
      },
      error: (err) => this.failed(err),
    });
  }

  protected commit(job: ImportJob): void {
    this.act(job, 'commit', 'Imported.');
  }

  protected async discard(job: ImportJob): Promise<void> {
    const yes = await this.confirm.ask({ title: 'Discard this file?', message: 'Nothing was imported from it. The stored file is deleted.', confirmLabel: 'Discard' });
    if (yes) {
      this.act(job, 'discard', 'Discarded.');
    }
  }

  protected async undo(job: ImportJob): Promise<void> {
    const yes = await this.confirm.ask({
      title: 'Undo this import?',
      message: 'Every student it created, with their enrollments and proposed guardians, is removed.',
      confirmLabel: 'Undo the import',
      tone: 'danger',
    });
    if (yes) {
      this.act(job, 'undo', 'Import undone.');
    }
  }
}
