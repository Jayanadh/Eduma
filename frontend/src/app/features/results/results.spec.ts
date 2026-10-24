import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AssessmentT, StudentRecord } from '../../core/api/types';
import { makeMe, signInAs } from '../../core/test-data';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { AssessmentPage } from './assessment-page';
import { DocumentsSection } from './documents-section';
import { SchemesPage } from './schemes-page';
import { VerifyPage } from './verify-page';

const ASSESSMENT: AssessmentT = {
  id: 'as1', version: 3, title: 'MAT101 end of term', state: 'draft', state_label: 'Marks being entered', returned_reason: '',
  term: { id: 't1', name: 'Semester 1' }, target: { kind: 'offering', id: 'o1', label: 'MAT101-A' }, subject: null,
  course: { id: 'c1', code: 'MAT101' },
  scheme: {
    id: 'sc1', version: 2, name: 'Theory', revision: 1, status: 'published', pass_percent: '40.00', decimals: 2, bands: [],
    components: [
      { id: 'i', name: 'Internal', max_marks: '40.00', weight: '40.00', min_percent: null },
      { id: 'f', name: 'Final', max_marks: '60.00', weight: '60.00', min_percent: '40.00' },
    ],
  },
  candidates: [{ id: 'k1', student: { id: 's1', number: '2026-0001', full_name: 'Asha Rao' }, marks: {}, result: null }],
  can_evaluate: true, cases: [], mappings: [], attainment: null,
}; // prettier-ignore

describe('Results pages', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ConfirmDialog, useValue: { prompt: () => Promise.resolve('Issued in error') } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    const officer = makeMe();
    officer.membership = {
      ...officer.membership!,
      modules_enabled: ['exams', 'report_cards'],
      permissions: ['assessment.manage', 'results.moderate', 'results.publish', 'student.read'],
    };
    await signInAs(officer);
  });

  function respond(url: string, body: unknown) {
    for (const request of http.match((r) => r.url === url)) {
      request.flush(body as object);
    }
  }

  it('saves a draft scheme with its components', async () => {
    const fixture = TestBed.createComponent(SchemesPage);
    await fixture.whenStable();
    respond('/api/v1/institution/results/schemes', []);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLInputElement>('#scheme-name')!.value = 'Theory 40/60';
    root.querySelector<HTMLFormElement>('#add-scheme')!.dispatchEvent(new Event('submit'));
    const body = http.expectOne((r) => r.method === 'POST').request.body;
    expect(body.name).toBe('Theory 40/60');
    expect(body.components).toEqual([
      { name: 'Internal', max_marks: '40', weight: '40', min_percent: null },
      { name: 'Final', max_marks: '60', weight: '60', min_percent: '40' },
    ]);
  });

  it('enters a score and an absence, never a zero, then submits', async () => {
    const fixture = TestBed.createComponent(AssessmentPage);
    fixture.componentRef.setInput('id', 'as1');
    await fixture.whenStable();
    respond('/api/v1/institution/results/assessments/as1', ASSESSMENT);
    await fixture.whenStable();
    respond('/api/v1/institution/results/courses/c1/outcomes', []);
    const root = fixture.nativeElement as HTMLElement;
    const score = root.querySelector<HTMLInputElement>('#score-k1-i')!;
    score.value = '32';
    score.dispatchEvent(new Event('input'));
    const final = root.querySelector<HTMLSelectElement>('#status-k1-f')!;
    final.value = 'absent';
    final.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Save marks')!.click();
    expect(http.expectOne('/api/v1/institution/results/assessments/as1/marks').request.body).toEqual({
      version: 3,
      marks: [
        { candidate: 'k1', component: 'i', status: 'scored', score: '32' },
        { candidate: 'k1', component: 'f', status: 'absent', score: null },
      ],
    });
  });

  it('issues a transcript and revokes a document with a reason', async () => {
    const fixture = TestBed.createComponent(DocumentsSection);
    fixture.componentRef.setInput('student', { id: 's1' } as StudentRecord);
    await fixture.whenStable();
    respond('/api/v1/institution/results/students/s1/documents', [
      { id: 'd1', kind: 'transcript', kind_label: 'Transcript', number: 'TR-2026-00001', title: 'Transcript', status: 'current',
        reason: '', issued_at: '2026-10-24T00:00:00Z', token: 'tok', content: {}, content_hash: 'x' },
    ]); // prettier-ignore
    respond('/api/v1/institution/academics/years', []);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    const kind = root.querySelector<HTMLSelectElement>('#doc-kind')!;
    kind.value = 'transcript';
    kind.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    root.querySelector<HTMLFormElement>('#issue-document')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne((r) => r.method === 'POST' && r.url.endsWith('/documents')).request.body).toEqual({ kind: 'transcript' });
    root.querySelector<HTMLButtonElement>('[aria-label="Revoke TR-2026-00001"]')!.click();
    await fixture.whenStable();
    expect(http.expectOne('/api/v1/institution/results/documents/d1/revoke').request.body).toEqual({ reason: 'Issued in error' });
  });

  it('shows the public check with status and initials only', async () => {
    const fixture = TestBed.createComponent(VerifyPage);
    fixture.componentRef.setInput('token', 'tok');
    await fixture.whenStable();
    http.expectOne('/api/v1/public/verify/tok').flush({
      institution: 'Meridian College', kind: 'Transcript', number: 'TR-2026-00001', issued_on: '2026-10-24', holder: 'A. Demo',
      status: 'superseded', superseded_by: 'TR-2026-00002',
    }); // prettier-ignore
    await fixture.whenStable();
    const text = (fixture.nativeElement as HTMLElement).textContent!;
    expect(text).toContain('Replaced by a newer document (TR-2026-00002)');
    expect(text).toContain('A. Demo');
  });
});
