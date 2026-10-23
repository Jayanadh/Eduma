import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { ImportJob, Page } from '../../core/api/types';
import { dateTime } from '../../core/format';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { Pager } from '../../ui/pager';

const COLUMNS =
  'source_record_id, full_name, date_of_birth (YYYY-MM-DD or unknown), phone, email, address, admitted_on, ' +
  'academic_year (e.g. 2026–27), place_code, place_label, campus_code, entry_date, guardian_name, ' +
  'guardian_relationship, guardian_phone, guardian_email';

/** Bring existing students in from a spreadsheet: checked first, imported only when you say so (SCR-042). */
@Component({
  selector: 'app-data-page',
  imports: [LoadError, PageHeader, Pager, RouterLink],
  template: `
    <div class="page">
      <app-page-header eyebrow="Settings" title="Data transfer" subtitle="Import students from your old system. Nothing changes until you have checked the file and chosen to import it." />
      <form class="card stack upload section" (submit)="$event.preventDefault(); send()">
        <h2 class="card-title">Import students</h2>
        <p class="small">Save the spreadsheet as <strong>CSV UTF-8</strong>, one student per row, with these columns: {{ columns }}.
          <a href="/api/v1/institution/imports/template.csv" download>Download the template</a>.</p>
        <div class="field">
          <label for="import-source">Where the data comes from</label>
          <input id="import-source" [value]="source()" (input)="source.set($any($event.target).value)" placeholder="e.g. Old ERP" />
          @if (errors()['source_system']; as m) { <span class="field-error">{{ m }}</span> }
        </div>
        <div class="field">
          <label for="import-file">File</label>
          <input id="import-file" type="file" accept=".csv,text/csv" (change)="file.set($any($event.target).files?.[0] ?? null)" />
          @if (errors()['file']; as m) { <span class="field-error">{{ m }}</span> }
        </div>
        @if (error()) { <p class="field-error" role="alert">{{ error() }}</p> }
        <div><button type="submit" class="btn btn-primary" [disabled]="busy()">{{ busy() ? 'Checking…' : 'Check the file' }}</button></div>
      </form>
      <app-load-error [message]="jobs.error()" (retry)="jobs.reload()" />
      @if (jobs.value(); as result) {
        @if (result.results.length) {
          <div class="card list-card section">
            <ul class="list">
              @for (job of result.results; track job.id) {
                <li>
                  <a class="list-row" [routerLink]="['/app/settings/data', job.id]">
                    <span class="list-main">
                      <span class="list-title">{{ job.original_name }} · {{ job.source_system }}</span>
                      <span class="muted small">{{ job.totals['rows'] }} rows · {{ dateTime(job.created_at) }}{{ job.created_by ? ' · ' + job.created_by : '' }}</span>
                    </span>
                    <span class="badge badge-info">{{ job.status_label }}</span>
                  </a>
                </li>
              }
            </ul>
          </div>
          <app-pager [page]="page()" [count]="result.count" (go)="page.set($event)" />
        }
      }
    </div>
  `,
})
export class DataPage {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  protected readonly columns = COLUMNS;
  protected readonly dateTime = dateTime;
  protected readonly page = signal(1);
  protected readonly jobs = load(
    () => this.api.get<Page<ImportJob>>('institution/imports', { page: this.page() }),
    () => this.page(),
  );
  protected readonly source = signal('');
  protected readonly file = signal<File | null>(null);
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly error = signal('');

  protected send(): void {
    const file = this.file();
    if (!file) {
      this.errors.set({ file: 'Choose a CSV file.' });
      return;
    }
    this.busy.set(true);
    this.errors.set({});
    this.error.set('');
    this.api.upload<ImportJob>('institution/imports', 'file', file, { source_system: this.source() }).subscribe({
      next: (job) => void this.router.navigate(['/app/settings/data', job.id]),
      error: (err) => {
        this.busy.set(false);
        this.errors.set(fieldErrors(err));
        if (!Object.keys(fieldErrors(err)).length) {
          this.error.set(apiErrorMessage(err));
        }
      },
    });
  }
}
