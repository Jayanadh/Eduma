import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { GuardianLink, StudentRecord } from '../../core/api/types';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { makeMe, signInAs } from '../../core/test-data';
import { StudentHome } from '../student/student-home';
import { GuardiansSection } from './guardians-section';
import { HistorySection } from './history-section';
import { StudentPage } from './student-page';
import { StudentsPage } from './students-page';

const ENROLLMENT = {
  academic_year: '2027–28',
  place_code: 'C6',
  place_label: 'Class 6',
  campus_name: 'Main campus',
  entry_date: '2027-06-01',
  status: 'active',
};

function record(overrides: Partial<StudentRecord> = {}): StudentRecord {
  return {
    id: 's1',
    number: '2027-0001',
    full_name: 'Arjun Demo',
    status: 'active',
    enrollment: ENROLLMENT,
    version: 3,
    date_of_birth: '2015-05-17',
    phone: '',
    email: '',
    address: '1 Lake Road',
    admitted_on: '2026-10-18',
    enrollments: [ENROLLMENT],
    application: { id: 'a1', number: 'A2027-0002' },
    login: 'aster.2027-0001',
    last_login: null,
    left_on: null,
    can_withdraw: true,
    can_reinstate: false,
    can_manage_guardians: true,
    ...overrides,
  };
}

describe('Student pages', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ConfirmDialog, useValue: { prompt: () => Promise.resolve('Moved away') } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  it('lists students a page at a time', async () => {
    const fixture = TestBed.createComponent(StudentsPage);
    await fixture.whenStable();
    const request = http.expectOne((r) => r.url === '/api/v1/institution/students');
    expect(request.request.params.get('page')).toBe('1');
    request.flush({ count: 1, next: null, previous: null, results: [record()] });
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('2027-0001');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Class 6');
  });

  it('corrects details with the version it started from', async () => {
    const registrar = makeMe();
    registrar.membership!.permissions = ['institution.read', 'student.read', 'student.update'];
    await signInAs(registrar);
    const fixture = TestBed.createComponent(StudentPage);
    fixture.componentRef.setInput('id', 's1');
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/students/s1').flush(record());
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    const name = root.querySelector<HTMLInputElement>('#student-name')!;
    name.value = 'Arjun R. Demo';
    name.dispatchEvent(new Event('input'));
    root.querySelector('form')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/students/s1');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body.version).toBe(3);
    expect(request.request.body.full_name).toBe('Arjun R. Demo');
  });

  it('shows students their own number and class', async () => {
    const fixture = TestBed.createComponent(StudentHome);
    await fixture.whenStable();
    http.expectOne('/api/v1/student/me').flush({
      number: '2027-0001',
      full_name: 'Arjun Demo',
      date_of_birth: '2015-05-17',
      status: 'active',
      enrollment: ENROLLMENT,
    });
    await fixture.whenStable();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('2027-0001');
    expect(text).toContain('Class 6');
    expect(text).toContain('2027–28');
  });

  function guardianLink(overrides: Partial<GuardianLink> = {}): GuardianLink {
    return {
      id: 'g1',
      version: 1,
      adult: { full_name: 'Asha Rao', phone: '+91 90000 12345', email: '' },
      relationship: 'Mother',
      status: 'proposed',
      status_label: 'Waiting for verification',
      in_effect: false,
      access: { record: false, fees: false, messages: false },
      starts_on: null,
      ends_on: null,
      has_login: false,
      source: 'enrollment',
      needs_adult_review: false,
      ...overrides,
    };
  }

  async function guardiansOf(links: GuardianLink[]) {
    const fixture = TestBed.createComponent(GuardiansSection);
    fixture.componentRef.setInput('student', record());
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/students/s1/guardians').flush(links);
    await fixture.whenStable();
    return fixture;
  }

  function buttonNamed(root: HTMLElement, text: string) {
    return [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!;
  }

  function type(root: HTMLElement, selector: string, value: string) {
    const field = root.querySelector<HTMLInputElement>(selector)!;
    field.value = value;
    field.dispatchEvent(new Event('input'));
  }

  it('verifies a link with its evidence, access and a new login', async () => {
    const fixture = await guardiansOf([guardianLink()]);
    const root = fixture.nativeElement as HTMLElement;
    buttonNamed(root, 'Verify').click();
    await fixture.whenStable();
    type(root, '#verify-reference', 'Aadhaar seen');
    const login = root.querySelector<HTMLInputElement>('#verify-login')!;
    login.checked = true;
    login.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    type(root, '#verify-username', 'asha.rao');
    type(root, '#verify-password', 'Welcome-2027-pass');
    root.querySelector<HTMLFormElement>('form.verify')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/students/s1/guardians/g1/verify');
    expect(request.request.body).toMatchObject({
      version: 1,
      authority_basis: 'parent',
      verification_method: 'documents_in_person',
      verification_reference: 'Aadhaar seen',
      access: { record: true, fees: false, messages: false },
      login: { username: 'asha.rao', password: 'Welcome-2027-pass' },
    });
  });

  it('asks why before revoking a link', async () => {
    const fixture = await guardiansOf([guardianLink({ status: 'active', status_label: 'Verified', in_effect: true })]);
    buttonNamed(fixture.nativeElement as HTMLElement, 'Revoke').click();
    await fixture.whenStable();
    const request = http.expectOne('/api/v1/institution/students/s1/guardians/g1/revoke');
    expect(request.request.body).toEqual({ version: 1, reason: 'Moved away' });
  });

  it('withdraws with the date and reason', async () => {
    await signInAs(makeMe());
    const fixture = TestBed.createComponent(StudentPage);
    fixture.componentRef.setInput('id', 's1');
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/students/s1').flush(record());
    await fixture.whenStable();
    for (const request of http.match(() => true)) {
      request.flush(request.request.url.endsWith('history') ? { count: 0, next: null, previous: null, results: [] } : []);
    }
    const root = fixture.nativeElement as HTMLElement;
    buttonNamed(root, 'Withdraw').click();
    await fixture.whenStable();
    type(root, '#withdraw-date', '2027-03-01');
    type(root, '#withdraw-reason', 'Family moved to Pune.');
    root.querySelector<HTMLFormElement>('form.withdraw')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/students/s1/withdraw');
    expect(request.request.body).toEqual({
      version: 3,
      effective_on: '2027-03-01',
      reason: 'Family moved to Pune.',
      clearance_note: '',
    });
  });

  it('shows the history newest first, a page at a time', async () => {
    const fixture = TestBed.createComponent(HistorySection);
    fixture.componentRef.setInput('studentId', 's1');
    await fixture.whenStable();
    const request = http.expectOne((r) => r.url === '/api/v1/institution/students/s1/history');
    expect(request.request.params.get('page')).toBe('1');
    request.flush({
      count: 2,
      next: null,
      previous: null,
      results: [
        { at: '2026-10-19T10:00:00Z', actor: 'Aster Registrar', action: 'student.withdrawn', summary: '2027-0001 withdrawn', changes: {} },
        { at: '2026-10-18T10:00:00Z', actor: 'Aster Registrar', action: 'student.enrolled', summary: '2027-0001 enrolled', changes: {} },
      ],
    });
    await fixture.whenStable();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text.indexOf('withdrawn')).toBeLessThan(text.indexOf('enrolled'));
  });

  it('filters the directory by status', async () => {
    const fixture = TestBed.createComponent(StudentsPage);
    await fixture.whenStable();
    http.expectOne((r) => r.url === '/api/v1/institution/students').flush({ count: 0, next: null, previous: null, results: [] });
    await fixture.whenStable();
    const select = (fixture.nativeElement as HTMLElement).querySelector<HTMLSelectElement>('#student-status')!;
    select.value = 'withdrawn';
    select.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    const request = http.expectOne((r) => r.url === '/api/v1/institution/students');
    expect(request.request.params.get('status')).toBe('withdrawn');
  });
});
