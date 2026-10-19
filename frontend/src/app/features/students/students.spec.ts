import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { StudentRecord } from '../../core/api/types';
import { makeMe, signInAs } from '../../core/test-data';
import { StudentHome } from '../student/student-home';
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
    ...overrides,
  };
}

describe('Student pages', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
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
});
