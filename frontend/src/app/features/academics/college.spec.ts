import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Course, Offering } from '../../core/api/types';
import { makeMe, signInAs } from '../../core/test-data';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { CoursesPage } from './courses-page';
import { OfferingPage } from './offering-page';
import { OfferingsPage } from './offerings-page';
import { SectionsPage } from './sections-page';
import { TeachingPage } from './teaching-page';

const EMPTY = { count: 0, next: null, previous: null, results: [] };
const PHY101: Course = {
  id: 'c1',
  version: 1,
  code: 'PHY101',
  title: 'Mechanics',
  credits: '4.0',
  kind: 'theory',
  kind_label: 'Theory',
  department: { id: 'd1', name: 'Physics' },
  is_active: true,
  can_manage: true,
};
const YEARS = [
  {
    id: 'y1',
    version: 1,
    code: '2026–27',
    starts_on: '2026-06-01',
    ends_on: '2027-03-31',
    status: 'current',
    status_label: 'Current',
    terms: [{ id: 't1', name: 'Semester 1', ordinal: 1, starts_on: '2026-06-01', ends_on: '2026-10-31' }],
  },
];

function offering(overrides: Partial<Offering> = {}): Offering {
  return {
    id: 'o1',
    version: 2,
    label: 'PHY101-A',
    code: 'A',
    capacity: 60,
    status: 'planned',
    status_label: 'Planned',
    course: { id: 'c1', code: 'PHY101', title: 'Mechanics', credits: '4.0' },
    term: { id: 't1', name: 'Semester 1', year: '2026–27', year_status: 'current' },
    campus: { id: 'm1', name: 'Main campus' },
    linked_to: null,
    linked: [],
    teachers: [],
    can_manage: true,
    ...overrides,
  };
}

function field(root: HTMLElement, id: string, value: string, event = 'change'): void {
  const box = root.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!;
  box.value = value;
  box.dispatchEvent(new Event(event));
}

describe('College academics', () => {
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
    registrar.membership = { ...registrar.membership!, category: 'college', permissions: ['academic_structure.manage'] };
    await signInAs(registrar);
  });

  function respond(url: string, body: unknown) {
    for (const request of http.match((r) => r.url === url)) {
      request.flush(body as object);
    }
  }

  it('searches the course catalogue and adds a course', async () => {
    const fixture = TestBed.createComponent(CoursesPage);
    await fixture.whenStable();
    respond('/api/v1/institution/academics/courses', { ...EMPTY, count: 1, results: [PHY101] });
    respond('/api/v1/institution/departments', { ...EMPTY, results: [{ id: 'd1', code: 'PHY', name: 'Physics', is_active: true }] });
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('PHY101 · Mechanics');
    const component = fixture.componentInstance as unknown as { search: { set(value: string): void } };
    component.search.set('mech');
    await fixture.whenStable();
    expect(http.expectOne((r) => r.url === '/api/v1/institution/academics/courses').request.params.get('search')).toBe('mech');
    field(root, 'new-code', 'PHY101L', 'input');
    field(root, 'new-title', 'Mechanics Lab', 'input');
    field(root, 'new-credits', '1', 'input');
    field(root, 'new-kind', 'lab');
    field(root, 'new-department', 'd1');
    root.querySelector<HTMLFormElement>('#add-course')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne((r) => r.method === 'POST');
    expect(request.request.body).toEqual({ code: 'PHY101L', title: 'Mechanics Lab', credits: '1', kind: 'lab', department: 'd1' });
  });

  it('adds an offering linked to the lecture it goes with', async () => {
    const fixture = TestBed.createComponent(OfferingsPage);
    await fixture.whenStable();
    respond('/api/v1/institution/academics/years', YEARS);
    respond('/api/v1/institution/campuses', { ...EMPTY, results: [{ id: 'm1', name: 'Main campus' }] });
    respond('/api/v1/institution/academics/offerings', { ...EMPTY, count: 1, results: [offering()] });
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('PHY101-A');
    const component = fixture.componentInstance as unknown as { choose(id: string, label: string): void };
    component.choose('c2', 'PHY101L Mechanics Lab');
    field(root, 'new-term', 't1');
    await fixture.whenStable();
    respond('/api/v1/institution/academics/offerings', { ...EMPTY, count: 1, results: [offering()] });
    await fixture.whenStable();
    field(root, 'new-campus', 'm1');
    field(root, 'new-code', 'A1', 'input');
    field(root, 'new-capacity', '30', 'input');
    field(root, 'new-link', 'o1');
    root.querySelector<HTMLFormElement>('#add-offering')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne((r) => r.method === 'POST');
    expect(request.request.body).toEqual({ course: 'c2', term: 't1', campus: 'm1', code: 'A1', capacity: 30, linked_to: 'o1' });
  });

  it('opens an offering and assigns its teacher', async () => {
    const fixture = TestBed.createComponent(OfferingPage);
    fixture.componentRef.setInput('id', 'o1');
    await fixture.whenStable();
    respond('/api/v1/institution/academics/offerings/o1', offering());
    respond('/api/v1/institution/academics/staff', [{ id: 'm9', full_name: 'Meridian Physics Faculty' }]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Open for registration')!.click();
    await fixture.whenStable();
    const opened = http.expectOne((r) => r.method === 'PATCH');
    expect(opened.request.body).toEqual({ version: 2, status: 'open' });
    opened.flush(offering({ status: 'open', status_label: 'Open', version: 3 }));
    await fixture.whenStable();
    field(root, 'new-teacher', 'm9');
    root.querySelector<HTMLFormElement>('#add-teacher')!.dispatchEvent(new Event('submit'));
    const added = http.expectOne('/api/v1/institution/academics/offerings/o1/teachers');
    expect(added.request.body).toEqual({ membership: 'm9' });
  });

  it('adds a college batch for a program rather than a grade', async () => {
    const fixture = TestBed.createComponent(SectionsPage);
    await fixture.whenStable();
    respond('/api/v1/institution/academics/years', YEARS);
    respond('/api/v1/institution/academics/programs', [{ id: 'p1', code: 'BSC-PHY', name: 'B.Sc Physics', is_active: true }]);
    respond('/api/v1/institution/campuses', { ...EMPTY, results: [{ id: 'm1', name: 'Main campus' }] });
    respond('/api/v1/institution/academics/sections', EMPTY);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('#new-grade')).toBeNull();
    field(root, 'new-code', 'BSC-PHY 2026 A', 'input');
    root.querySelector<HTMLFormElement>('#add-section')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne((r) => r.method === 'POST');
    expect(request.request.body).toEqual({ year: 'y1', program: 'p1', campus: 'm1', code: 'BSC-PHY 2026 A', capacity: 40 });
  });

  it("lists a teacher's offerings beside their batches", async () => {
    const fixture = TestBed.createComponent(TeachingPage);
    await fixture.whenStable();
    respond('/api/v1/teaching/classes', [
      { section: { id: 's1', code: 'BSC-PHY 2026 A', grade: 'B.Sc Physics', year: '2026–27' }, subjects: [], class_teacher: true },
      {
        offering: { id: 'o1', course: 'PHY101', title: 'Mechanics', code: 'A', term: 'Semester 1', year: '2026–27' },
        subjects: [],
        class_teacher: false,
      },
    ]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('BSC-PHY 2026 A · B.Sc Physics');
    expect(root.textContent).toContain('PHY101-A · Mechanics · Semester 1');
    expect(root.querySelectorAll('a.list-row').length).toBe(1);
  });
});
