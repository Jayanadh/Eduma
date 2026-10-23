import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ImportJob, ImportRow } from '../../core/api/types';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { DataPage } from './data-page';
import { ImportPage } from './import-page';

const EMPTY = { count: 0, next: null, previous: null, results: [] };

function job(overrides: Partial<ImportJob> = {}): ImportJob {
  return {
    id: 'j1',
    version: 1,
    source_system: 'Old ERP',
    original_name: 'students.csv',
    status: 'validated',
    status_label: 'Checked, not imported',
    totals: { rows: 3, valid: 1, error: 1, duplicate: 1, unchanged: 0, changed: 0 },
    undecided: 1,
    created_at: '2026-10-23T10:00:00Z',
    created_by: 'Asha Rao',
    committed_at: null,
    ...overrides,
  };
}

const DUPLICATE: ImportRow = {
  id: 'r2',
  row_number: 3,
  source_record_id: 'S-2',
  full_name: 'Meera Rao',
  state: 'duplicate',
  state_label: 'Possible duplicate',
  errors: [],
  duplicate_of: [{ kind: 'student', id: 's1', label: '2027-0001 Meera Rao' }],
  decision: '',
  student: null,
};

describe('Data transfer', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ConfirmDialog, useValue: { ask: () => Promise.resolve(true) } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  it('uploads the file with its source system', async () => {
    const fixture = TestBed.createComponent(DataPage);
    await fixture.whenStable();
    http.expectOne((r) => r.url === '/api/v1/institution/imports').flush(EMPTY);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    const source = root.querySelector<HTMLInputElement>('#import-source')!;
    source.value = 'Old ERP';
    source.dispatchEvent(new Event('input'));
    const input = root.querySelector<HTMLInputElement>('#import-file')!;
    Object.defineProperty(input, 'files', { value: [new File(['a,b'], 'students.csv', { type: 'text/csv' })] });
    input.dispatchEvent(new Event('change'));
    root.querySelector<HTMLFormElement>('form.upload')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne((r) => r.url === '/api/v1/institution/imports' && r.method === 'POST');
    const body = request.request.body as FormData;
    expect(body.get('source_system')).toBe('Old ERP');
    expect((body.get('file') as File).name).toBe('students.csv');
  });

  async function batch(body: ImportJob, rows: ImportRow[] = [DUPLICATE]) {
    const fixture = TestBed.createComponent(ImportPage);
    fixture.componentRef.setInput('id', 'j1');
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/imports/j1').flush(body);
    http.expectOne((r) => r.url === '/api/v1/institution/imports/j1/rows').flush({ ...EMPTY, count: rows.length, results: rows });
    await fixture.whenStable();
    return fixture;
  }

  function button(root: HTMLElement, text: string) {
    return [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!;
  }

  it('decides duplicates and commits only when all are decided', async () => {
    const fixture = await batch(job());
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('2027-0001 Meera Rao');
    expect(button(root, 'Import').disabled).toBe(true);
    button(root, 'Skip').click();
    const decided = http.expectOne('/api/v1/institution/imports/j1/rows/r2/decide');
    expect(decided.request.body).toEqual({ decision: 'skip' });
    decided.flush({ ...DUPLICATE, decision: 'skip' });
    http.expectOne('/api/v1/institution/imports/j1').flush(job({ undecided: 0 }));
    await fixture.whenStable();
    expect(button(root, 'Import').disabled).toBe(false);
    button(root, 'Import').click();
    const commit = http.expectOne('/api/v1/institution/imports/j1/commit');
    expect(commit.request.body).toEqual({ version: 1 });
  });

  it('filters rows by state', async () => {
    const fixture = await batch(job());
    const select = (fixture.nativeElement as HTMLElement).querySelector<HTMLSelectElement>('#row-state')!;
    select.value = 'error';
    select.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    const request = http.expectOne((r) => r.url === '/api/v1/institution/imports/j1/rows');
    expect(request.request.params.get('state')).toBe('error');
  });

  it('asks before undoing an import', async () => {
    const fixture = await batch(job({ status: 'committed', status_label: 'Imported', undecided: 0, undo_blocker: null }), []);
    button(fixture.nativeElement as HTMLElement, 'Undo this import').click();
    await fixture.whenStable();
    const undo = http.expectOne('/api/v1/institution/imports/j1/undo');
    expect(undo.request.body).toEqual({ version: 1 });
  });
});
