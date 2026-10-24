import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { DegreeProgress, Registration, StudentRecord } from '../../core/api/types';
import { makeMe, signInAs } from '../../core/test-data';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { OfferingRegistrations } from '../academics/offering-registrations';
import { WindowsSection } from '../academics/windows-section';
import { RecordSection } from './record-section';
import { RegistrationSection } from './registration-section';

const EMPTY = { count: 0, next: null, previous: null, results: [] };
const STUDENT = { id: 's1', number: '2026-0001', full_name: 'Ananya Demo', version: 3 } as StudentRecord;
const REG: Registration = {
  id: 'r1', version: 4, state: 'pending_approval', state_label: 'Waiting for approval', reason_code: '',
  offering: { id: 'o1', label: 'PHY201-A', title: 'Electromagnetism', credits: '4.0', term: 'Semester 2' },
  student: { id: 's1', number: '2026-0001', full_name: 'Ananya Demo' }, attempt_no: null, regulation: 'R2026 rev 1',
  overrides: [], created_at: '2026-10-20T00:00:00Z',
}; // prettier-ignore
const PROGRESS: DegreeProgress = {
  advisory: true, note: 'Advisory', program: null, regulation: 'BSC-PHY R2026 rev 1', repeat_rule: 'replace', cgpa: null,
  terms: [], credits: { required: '120.0', earned: '0.0', accepted: '0.0', in_progress: '4.0', planned: '116.0', unmet: '116.0' },
  courses: [],
  attempts: [{ id: 'a1', course: 'PHY201', title: 'Electromagnetism', attempt_no: 1, term: 'Semester 2', year: '2026–27', credits: '4.0', outcome: 'in_progress', outcome_label: 'In progress', grade_point: null }],
  transfers: [{ id: 't1', version: 1, source_institution: 'Elsewhere', source_course: 'Mechanics I', source_credits: '4.0', evidence: 'Transcript', decision: 'pending', decision_label: 'Waiting for a decision', approved_credits: null, course: null, category: '', awarding_authority: '' }],
}; // prettier-ignore

describe('Registration and records for staff', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ConfirmDialog, useValue: { ask: () => Promise.resolve(true) } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    const registrar = makeMe();
    registrar.membership = {
      ...registrar.membership!,
      category: 'college',
      permissions: ['student.read', 'registration.manage', 'registration.override', 'academic_record.manage'],
    };
    await signInAs(registrar);
  });

  function respond(url: string, body: unknown) {
    for (const request of http.match((r) => r.url === url)) {
      request.flush(body as object);
    }
  }

  function set(root: HTMLElement, id: string, value: string) {
    const field = root.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!;
    field.value = value;
    field.dispatchEvent(new Event('change'));
  }

  it('opens a registration window for a term without one', async () => {
    const fixture = TestBed.createComponent(WindowsSection);
    await fixture.whenStable();
    respond('/api/v1/institution/academics/windows', []);
    respond('/api/v1/institution/academics/years', [
      { id: 'y1', code: '2026–27', status: 'current', terms: [{ id: 't2', name: 'Semester 2' }] },
    ]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    set(root, 'window-opens', '2026-10-15');
    set(root, 'window-closes', '2026-11-15');
    set(root, 'window-drop', '2026-11-30');
    root.querySelector<HTMLFormElement>('#add-window')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne((r) => r.method === 'POST').request.body).toEqual({
      term: 't2', opens_on: '2026-10-15', closes_on: '2026-11-15', drop_until: '2026-11-30', max_credits: '24', needs_approval: false,
    }); // prettier-ignore
  });

  it("approves an offering's pending registration with its version", async () => {
    const fixture = TestBed.createComponent(OfferingRegistrations);
    fixture.componentRef.setInput('offering', 'o1');
    await fixture.whenStable();
    respond('/api/v1/institution/academics/registrations', { ...EMPTY, count: 1, results: [REG] });
    await fixture.whenStable();
    (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('[aria-label="Approve 2026-0001"]')!.click();
    expect(http.expectOne('/api/v1/institution/academics/registrations/r1/approve').request.body).toEqual({ version: 4 });
  });

  it('registers a student and places a hold from their record', async () => {
    const fixture = TestBed.createComponent(RegistrationSection);
    fixture.componentRef.setInput('student', STUDENT);
    await fixture.whenStable();
    respond('/api/v1/institution/academics/registrations', EMPTY);
    respond('/api/v1/institution/academics/students/s1/holds', []);
    respond('/api/v1/institution/academics/overrides', []);
    respond('/api/v1/institution/academics/offerings', {
      ...EMPTY, results: [{ id: 'o1', label: 'PHY201-A', status: 'open', course: { title: 'Electromagnetism' }, term: { name: 'Semester 2' } }],
    }); // prettier-ignore
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLFormElement>('#register-for')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne((r) => r.method === 'POST').request.body).toEqual({ student: 's1', offerings: ['o1'], waitlist: false });
    set(root, 'hold-reason', 'Library fine');
    root.querySelector<HTMLFormElement>('#place-hold')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne('/api/v1/institution/academics/students/s1/holds').request.body).toEqual({ kind: 'academic', reason: 'Library fine' });
  });

  it('records an outcome and decides transfer credit', async () => {
    const fixture = TestBed.createComponent(RecordSection);
    fixture.componentRef.setInput('student', STUDENT);
    await fixture.whenStable();
    respond('/api/v1/institution/academics/students/s1/progress', PROGRESS);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    set(root, 'outcome-gp', '8.5');
    root.querySelector<HTMLFormElement>('#record-outcome')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne('/api/v1/institution/academics/attempts/a1').request.body).toEqual({ outcome: 'passed', grade_point: '8.5' });
    root.querySelector<HTMLButtonElement>('[aria-label="Reject Mechanics I"]')!.click();
    expect(http.expectOne('/api/v1/institution/academics/transfers/t1/decide').request.body).toEqual({ version: 1, decision: 'rejected' });
  });
});
