import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ClassSection } from '../../core/api/types';
import { ToastService } from '../../ui/toast';
import { SectionPage } from './section-page';
import { SectionsPage } from './sections-page';
import { TeachingPage } from './teaching-page';
import { TeachingRosterPage } from './teaching-roster-page';

const EMPTY = { count: 0, next: null, previous: null, results: [] };
const YEARS = [
  { id: 'y1', version: 1, code: '2026–27', starts_on: '2026-06-01', ends_on: '2027-03-31', status: 'current', status_label: 'Current', terms: [] },
  { id: 'y2', version: 1, code: '2027–28', starts_on: '2027-06-01', ends_on: '2028-03-31', status: 'planned', status_label: 'Planned', terms: [] },
];

function section(overrides: Partial<ClassSection> = {}): ClassSection {
  return {
    id: 's6a',
    version: 3,
    code: '6A',
    capacity: 40,
    placed: 1,
    year: { id: 'y1', code: '2026–27', status: 'current' },
    grade: { id: 'g6', name: 'Class 6' },
    campus: { id: 'c1', name: 'Main campus' },
    class_teacher: null,
    teachers: [],
    can_manage: true,
    ...overrides,
  };
}

describe('Sections', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  function respond(url: string, body: object) {
    for (const request of http.match((r) => r.url === url)) {
      request.flush(body);
    }
  }

  it('lists sections for the chosen year', async () => {
    const fixture = TestBed.createComponent(SectionsPage);
    await fixture.whenStable();
    respond('/api/v1/institution/academics/years', YEARS);
    respond('/api/v1/institution/academics/grades', []);
    respond('/api/v1/institution/campuses', EMPTY);
    respond('/api/v1/institution/academics/sections', { ...EMPTY, count: 1, results: [section()] });
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('6A');
    expect(root.textContent).toContain('1 of 40');
    const year = root.querySelector<HTMLSelectElement>('#filter-year')!;
    year.value = 'y2';
    year.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    const request = http.expectOne((r) => r.url === '/api/v1/institution/academics/sections');
    expect(request.request.params.get('year')).toBe('y2');
  });

  async function open(body: ClassSection) {
    const fixture = TestBed.createComponent(SectionPage);
    fixture.componentRef.setInput('id', 's6a');
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/academics/sections/s6a').flush(body);
    await fixture.whenStable();
    respond('/api/v1/institution/academics/sections/s6a/students', [
      { period: 'p1', student: { id: 'st1', number: '2026-0001', full_name: 'Kiran Rao' }, status: 'active', is_repeat: false },
    ]);
    respond('/api/v1/institution/academics/staff', [{ id: 'm9', full_name: 'Tara Teacher' }]);
    respond('/api/v1/institution/academics/subjects', [{ id: 'sci', version: 1, code: 'SCI', name: 'Science', is_active: true }]);
    respond('/api/v1/institution/academics/sections', { ...EMPTY, count: 2, results: [section(), section({ id: 's7a', code: '7A', year: { id: 'y2', code: '2027–28', status: 'planned' } })] });
    await fixture.whenStable();
    return fixture;
  }

  function button(root: HTMLElement, text: string) {
    return [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!;
  }

  it('places chosen students and says when the section is full', async () => {
    const fixture = await open(section());
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Kiran Rao');
    const page = fixture.componentInstance as unknown as { choose: (id: string, label: string) => void };
    page.choose('st2', '2026-0002 Asha Devi');
    await fixture.whenStable();
    const show = vi.spyOn(TestBed.inject(ToastService), 'show');
    button(root, 'Place 1 student').click();
    const place = http.expectOne((r) => r.url === '/api/v1/institution/academics/sections/s6a/students' && r.method === 'POST');
    expect(place.request.body).toEqual({ students: ['st2'] });
    place.flush({ title: 'Refused', status: 409, code: 'section_full', detail: '6A has room for 0 more.' }, { status: 409, statusText: 'Conflict' });
    await fixture.whenStable();
    expect(show).toHaveBeenCalledWith('6A has room for 0 more.', 'danger');
  });

  it('adds a teacher with a subject', async () => {
    const fixture = await open(section());
    const root = fixture.nativeElement as HTMLElement;
    const who = root.querySelector<HTMLSelectElement>('#teacher-who')!;
    who.value = 'm9';
    who.dispatchEvent(new Event('change'));
    const subject = root.querySelector<HTMLSelectElement>('#teacher-subject')!;
    subject.value = 'sci';
    subject.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    button(root, 'Add teacher').click();
    const request = http.expectOne('/api/v1/institution/academics/sections/s6a/teachers');
    expect(request.request.body).toEqual({ membership: 'm9', subject: 'sci' });
  });

  it('previews a move up and moves only those who can go', async () => {
    const fixture = await open(section());
    const root = fixture.nativeElement as HTMLElement;
    const target = root.querySelector<HTMLSelectElement>('#moveup-target')!;
    target.value = 's7a';
    target.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    button(root, 'Preview').click();
    const preview = http.expectOne('/api/v1/institution/academics/sections/s6a/move-up/preview');
    expect(preview.request.body).toEqual({ target: 's7a', mode: 'promote' });
    preview.flush([
      { student: { id: 'st1', number: '2026-0001', full_name: 'Kiran Rao' }, action: 'move' },
      { student: { id: 'st3', number: '2026-0003', full_name: 'Left Early' }, action: 'withdrawn' },
    ]);
    await fixture.whenStable();
    expect(root.textContent).toContain('Withdrawn');
    button(root, 'Move 1 student').click();
    const commit = http.expectOne('/api/v1/institution/academics/sections/s6a/move-up');
    expect(commit.request.body).toEqual({ target: 's7a', mode: 'promote', students: ['st1'] });
  });

  it('shows a teacher their classes and a roster', async () => {
    const fixture = TestBed.createComponent(TeachingPage);
    await fixture.whenStable();
    http.expectOne('/api/v1/teaching/classes').flush([
      { section: { id: 's6a', code: '6A', grade: 'Class 6', year: '2026–27' }, subjects: ['Science'], class_teacher: true },
    ]);
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Science');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Class teacher');
    const roster = TestBed.createComponent(TeachingRosterPage);
    roster.componentRef.setInput('id', 's6a');
    await roster.whenStable();
    http.expectOne('/api/v1/teaching/classes/s6a/students').flush([{ number: '2026-0001', full_name: 'Kiran Rao', status: 'active' }]);
    await roster.whenStable();
    expect((roster.nativeElement as HTMLElement).textContent).toContain('Kiran Rao');
  });
});
