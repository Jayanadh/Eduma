import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { AttendanceSessionT, Timetable } from '../../core/api/types';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { TeachingPage } from '../academics/teaching-page';
import { TimetablePage } from '../academics/timetable-page';
import { StudentAssignmentsPage } from '../student/assignments-page';
import { AttendancePage } from './attendance-page';
import { ClassTools } from './class-tools';
import { CorrectionsPage } from './corrections-page';

const SESSION: AttendanceSessionT = {
  id: 'a1', version: 2, state: 'draft', state_label: 'Saved, not submitted', date: '2026-10-24',
  target: { kind: 'section', id: 's1', label: '6A' }, submitted_at: null, unmarked: 2,
  roster: [
    { student: { id: 'k', number: '2026-0001', full_name: 'Kiran Rao' }, code: null, reason: '', mark: null },
    { student: { id: 'm', number: '2026-0002', full_name: 'Meera Iyer' }, code: null, reason: '', mark: null },
  ],
}; // prettier-ignore

describe('Attendance pages', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), { provide: ConfirmDialog, useValue: {} }],
    });
    http = TestBed.inject(HttpTestingController);
  });

  function respond(url: string, body: unknown) {
    for (const request of http.match((r) => r.url === url)) {
      request.flush(body as object);
    }
  }

  it('marks a register and submits it with the saved version', async () => {
    const fixture = TestBed.createComponent(AttendancePage);
    fixture.componentRef.setInput('id', 'a1');
    await fixture.whenStable();
    respond('/api/v1/teaching/attendance/a1', SESSION);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Everyone present')!.click();
    const absent = root.querySelector<HTMLInputElement>('#code-m-absent')!;
    absent.checked = true;
    absent.dispatchEvent(new Event('change'));
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Submit')!.click();
    const saved = http.expectOne('/api/v1/teaching/attendance/a1/marks');
    expect(saved.request.body).toEqual({ version: 2, marks: [{ student: 'k', code: 'present' }, { student: 'm', code: 'absent' }] });
    saved.flush({ ...SESSION, version: 3 });
    expect(http.expectOne('/api/v1/teaching/attendance/a1/submit').request.body).toEqual({ version: 3 });
  });

  it('asks for a correction on a submitted mark', async () => {
    const fixture = TestBed.createComponent(AttendancePage);
    fixture.componentRef.setInput('id', 'a1');
    await fixture.whenStable();
    const sent = { ...SESSION, state: 'submitted' as const, roster: [{ ...SESSION.roster[0], code: 'absent' as const, mark: 'mk1' }] };
    respond('/api/v1/teaching/attendance/a1', sent);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLButtonElement>('[aria-label="Correct Kiran Rao"]')!.click();
    await fixture.whenStable();
    root.querySelector<HTMLInputElement>('#fix-reason-mk1')!.value = 'Was at the nurse';
    root.querySelector<HTMLFormElement>('#fix-mk1')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne('/api/v1/teaching/attendance/marks/mk1/corrections').request.body).toEqual({ code: 'present', reason: 'Was at the nurse' });
  });

  it('approves a correction', async () => {
    const fixture = TestBed.createComponent(CorrectionsPage);
    await fixture.whenStable();
    respond('/api/v1/institution/attendance/corrections', [
      { id: 'c1', state: 'requested', previous_code: 'absent', new_code: 'present', reason: 'Nurse', date: '2026-10-24', label: '6A',
        student: { number: '2026-0001', full_name: 'Kiran Rao' }, requested_by: 'Teacher' },
    ]); // prettier-ignore
    await fixture.whenStable();
    (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('[aria-label="Approve 2026-0001"]')!.click();
    expect(http.expectOne('/api/v1/institution/attendance/corrections/c1/approve').request.method).toBe('POST');
  });

  it('opens a register for a class and day', async () => {
    const fixture = TestBed.createComponent(ClassTools);
    fixture.componentRef.setInput('kind', 'section');
    fixture.componentRef.setInput('target', 's1');
    await fixture.whenStable();
    respond('/api/v1/teaching/assignments', []);
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLInputElement>('#attendance-date')!.value = '2026-10-23';
    root.querySelector<HTMLFormElement>('#take-attendance')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/teaching/attendance');
    expect(request.request.body).toEqual({ section: 's1', date: '2026-10-23' });
    request.flush(SESSION);
    expect(navigate).toHaveBeenCalledWith(['/app/teaching/attendance', 'a1']);
  });

  it("starts a register from the day's timetabled lesson", async () => {
    const fixture = TestBed.createComponent(TeachingPage);
    await fixture.whenStable();
    respond('/api/v1/teaching/classes', []);
    respond('/api/v1/teaching/day', [
      { id: 'sl1', weekday: 6, starts_at: '09:00', ends_at: '09:45', target: { kind: 'section', id: 's1', label: '6A' }, subject: 'Science',
        room: null, teacher: null, substitute: false, session: null },
    ]); // prettier-ignore
    await fixture.whenStable();
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Take attendance')!.click();
    const body = http.expectOne('/api/v1/teaching/attendance').request.body;
    expect(body).toEqual({ section: 's1', date: expect.any(String), slot: 'sl1' });
  });

  it('adds a lesson to a draft timetable and shows clashes', async () => {
    const fixture = TestBed.createComponent(TimetablePage);
    await fixture.whenStable();
    respond('/api/v1/institution/academics/years', [{ id: 'y1', code: '2026–27', status: 'current', terms: [{ id: 't1', name: 'Term 1' }] }]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    const term = root.querySelector<HTMLSelectElement>('#tt-term')!;
    term.value = 't1';
    term.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    const draft: Timetable = {
      id: 'tt1', version: 1, number: 1, status: 'draft', status_label: 'Draft', term: { id: 't1', name: 'Term 1', year: '2026–27' },
      slots: [], conflicts: [{ kind: 'room', slots: ['a', 'b'], weekday: 1, detail: '6A and 6B share a room' }],
    }; // prettier-ignore
    respond('/api/v1/institution/academics/timetables', [draft]);
    respond('/api/v1/institution/academics/sections', { count: 1, next: null, previous: null, results: [{ id: 's1', code: '6A', level: 'Class 6' }] });
    await fixture.whenStable();
    expect(root.textContent).toContain('6A and 6B share a room');
    root.querySelector<HTMLFormElement>('#add-slot')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne((r) => r.url === '/api/v1/institution/academics/timetables/tt1/slots');
    expect(request.request.body).toEqual({ weekday: 1, starts_at: '09:00', ends_at: '09:45', section: 's1', subject: null, room: null, teacher: null });
  });

  it('lets a student hand in an answer', async () => {
    const fixture = TestBed.createComponent(StudentAssignmentsPage);
    await fixture.whenStable();
    respond('/api/v1/student/assignments', [
      { id: 'as1', title: 'Plant cells', instructions: 'Draw one.', due_at: '2026-10-30T10:00:00Z', target: { kind: 'section', id: 's1', label: '6A' }, submission: null },
    ]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLTextAreaElement>('#answer-text-as1')!.value = 'A cell wall';
    root.querySelector<HTMLFormElement>('#answer-as1')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne('/api/v1/student/assignments/as1/submit').request.body).toEqual({ text: 'A cell wall' });
  });
});
