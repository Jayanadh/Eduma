import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AcademicYear } from '../../core/api/types';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { SetupPage } from './setup-page';

const YEAR: AcademicYear = {
  id: 'y1',
  version: 1,
  code: '2026–27',
  starts_on: '2026-06-01',
  ends_on: '2027-03-31',
  status: 'current',
  status_label: 'Current',
  terms: [{ id: 't1', name: 'Term 1', ordinal: 1, starts_on: '2026-06-01', ends_on: '2026-10-31' }],
};

describe('Academic setup', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ConfirmDialog, useValue: { prompt: () => Promise.resolve('Grade 6') } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  async function open() {
    const fixture = TestBed.createComponent(SetupPage);
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/academics/years').flush([YEAR]);
    http.expectOne('/api/v1/institution/academics/grades').flush([{ id: 'g6', version: 2, code: 'C6', name: 'Class 6', order: 6, is_active: true }]);
    http.expectOne('/api/v1/institution/academics/subjects').flush([]);
    await fixture.whenStable();
    return fixture;
  }

  function type(root: HTMLElement, id: string, value: string) {
    const field = root.querySelector<HTMLInputElement>(`#${id}`)!;
    field.value = value;
    field.dispatchEvent(new Event('input'));
  }

  it('lists years with their terms and adds a year', async () => {
    const fixture = await open();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('2026–27');
    expect(root.textContent).toContain('Term 1');
    type(root, 'year-code', '2027–28');
    type(root, 'year-start', '2027-06-01');
    type(root, 'year-end', '2028-03-31');
    root.querySelector<HTMLFormElement>('form.add-year')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/academics/years');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ code: '2027–28', starts_on: '2027-06-01', ends_on: '2028-03-31' });
    request.flush({ title: 'Check', status: 422, errors: [{ field: 'starts_on', code: 'invalid', message: 'This overlaps 2026–27.' }] }, { status: 422, statusText: 'Unprocessable' });
    await fixture.whenStable();
    expect(root.textContent).toContain('This overlaps 2026–27.');
  });

  it('adds a term to a year', async () => {
    const fixture = await open();
    const root = fixture.nativeElement as HTMLElement;
    type(root, 'term-name-y1', 'Term 2');
    type(root, 'term-start-y1', '2026-11-01');
    type(root, 'term-end-y1', '2027-03-31');
    root.querySelector<HTMLFormElement>('form.add-term')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/academics/years/y1/terms');
    expect(request.request.body).toEqual({ name: 'Term 2', ordinal: 2, starts_on: '2026-11-01', ends_on: '2027-03-31' });
  });

  it('renames a grade with its version and adds a subject', async () => {
    const fixture = await open();
    const root = fixture.nativeElement as HTMLElement;
    [...root.querySelectorAll('button')].find((b) => b.getAttribute('aria-label') === 'Rename Class 6')!.click();
    await fixture.whenStable();
    const rename = http.expectOne('/api/v1/institution/academics/grades/g6');
    expect(rename.request.body).toEqual({ version: 2, name: 'Grade 6' });
    type(root, 'subject-code', 'SCI');
    type(root, 'subject-name', 'Science');
    root.querySelector<HTMLFormElement>('form.add-subject')!.dispatchEvent(new Event('submit'));
    const add = http.expectOne('/api/v1/institution/academics/subjects');
    expect(add.request.body).toEqual({ code: 'SCI', name: 'Science' });
  });
});
