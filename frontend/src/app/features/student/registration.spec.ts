import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { DegreeProgress, OwnRegistration } from '../../core/api/types';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { ProgressPage } from './progress-page';
import { RegistrationPage } from './registration-page';

const PAGE: OwnRegistration = {
  window: {
    id: 'w1', version: 1, term: 'Semester 2', term_id: 't2', year: '2026–27', opens_on: '2026-10-15',
    closes_on: '2026-11-15', drop_until: '2026-11-30', max_credits: '24.0', needs_approval: false, open: true,
  },
  offerings: [
    { id: 'o1', label: 'PHY201-A', title: 'Electromagnetism', credits: '4.0', seats_left: 1, linked_to: null, labs: [], problems: [] },
    { id: 'o2', label: 'MAT201-A', title: 'Linear algebra', credits: '4.0', seats_left: 9, linked_to: null, labs: [], problems: ['prerequisite'] },
  ],
  registrations: [
    {
      id: 'r1', version: 2, state: 'registered', state_label: 'Registered', reason_code: '',
      offering: { id: 'o9', label: 'PHY101-A', title: 'Mechanics', credits: '4.0', term: 'Semester 1' },
      student: { id: 's1', number: '2026-0001', full_name: 'Ananya Demo' }, attempt_no: 1, regulation: 'R2026 rev 1',
      overrides: [], created_at: '2026-06-01T00:00:00Z',
    },
  ],
}; // prettier-ignore

describe('Student registration and progress', () => {
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

  async function open() {
    const fixture = TestBed.createComponent(RegistrationPage);
    await fixture.whenStable();
    http.expectOne('/api/v1/student/registration').flush(PAGE);
    await fixture.whenStable();
    return fixture;
  }

  function button(root: HTMLElement, text: string) {
    return [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!;
  }

  it('shows what stops a choice and confirms the chosen offerings', async () => {
    const fixture = await open();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Prerequisite not passed yet');
    const box = root.querySelector<HTMLInputElement>('#choose-o1')!;
    box.checked = true;
    box.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(root.textContent).toContain('1 chosen · 4 credits');
    button(root, 'Confirm registration').click();
    const request = http.expectOne('/api/v1/student/registration');
    expect(request.request.body).toEqual({ offerings: ['o1'], waitlist: false });
    request.flush({ type: 'x', title: 'x', status: 409, code: 'capacity_exhausted', detail: 'PHY201-A has no seats left.' }, { status: 409, statusText: 'Conflict' });
    await fixture.whenStable();
    expect(root.textContent).toContain('not confirmed');
    button(root, 'Join the waitlist').click();
    expect(http.expectOne('/api/v1/student/registration').request.body).toEqual({ offerings: ['o1'], waitlist: true });
  });

  it('drops a registration with its version', async () => {
    const fixture = await open();
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLButtonElement>('[aria-label="Drop PHY101-A"]')!.click();
    await fixture.whenStable();
    expect(http.expectOne('/api/v1/student/registrations/r1/drop').request.body).toEqual({ version: 2 });
  });

  it('shows degree progress as advisory', async () => {
    const progress: DegreeProgress = {
      advisory: true, note: 'Advisory progress against the regulation — not an award or a transcript.',
      program: { code: 'BSC-PHY', name: 'B.Sc Physics' }, regulation: 'BSC-PHY R2026 rev 1', repeat_rule: 'replace',
      cgpa: '7.57', terms: [{ term: 'Semester 1', year: '2026–27', sgpa: '7.57' }],
      credits: { required: '120.0', earned: '7.0', accepted: '7.0', in_progress: '4.0', planned: '109.0', unmet: '109.0' },
      courses: [{ code: 'PHY201', title: 'Electromagnetism', credits: '4.0', category: 'core', term: 3, status: 'in_progress', attempts: 1, prerequisites_met: true }],
      attempts: [], transfers: [],
    }; // prettier-ignore
    const fixture = TestBed.createComponent(ProgressPage);
    await fixture.whenStable();
    http.expectOne('/api/v1/student/progress').flush(progress);
    await fixture.whenStable();
    const text = (fixture.nativeElement as HTMLElement).textContent!;
    expect(text).toContain('not an award');
    expect(text).toContain('7.57');
    expect(text).toContain('7.0 / 120.0');
    expect(text).toContain('In progress');
  });
});
