import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { Curriculum, Program } from '../../core/api/types';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { CurriculumPage } from './curriculum-page';
import { ProgramPage } from './program-page';
import { ProgramsPage } from './programs-page';

const EMPTY = { count: 0, next: null, previous: null, results: [] };
const BSC: Program = {
  id: 'p1',
  version: 1,
  code: 'BSC-PHY',
  name: 'B.Sc Physics',
  qualification: 'B.Sc',
  length_terms: 6,
  department: { id: 'd1', name: 'Physics' },
  is_active: true,
  can_manage: true,
};

function curriculum(overrides: Partial<Curriculum> = {}): Curriculum {
  return {
    id: 'cv1',
    version: 4,
    regulation: 'R2026',
    revision: 1,
    cohort: 2026,
    credits_required: '120.0',
    status: 'draft',
    status_label: 'Draft',
    published_at: null,
    program: { id: 'p1', code: 'BSC-PHY', name: 'B.Sc Physics', length_terms: 6 },
    total_credits: '8.0',
    terms: [
      {
        term: 1,
        courses: [
          {
            id: 'e1',
            course: { id: 'c1', code: 'PHY101', title: 'Mechanics', credits: '4.0', kind: 'theory' },
            category: 'core',
            category_label: 'Core',
            term: 1,
            elective_group: '',
            prerequisites: [],
          },
        ],
      },
      {
        term: 3,
        courses: [
          {
            id: 'e2',
            course: { id: 'c2', code: 'PHY201', title: 'Electromagnetism', credits: '4.0', kind: 'theory' },
            category: 'core',
            category_label: 'Core',
            term: 3,
            elective_group: '',
            prerequisites: ['PHY101'],
          },
        ],
      },
    ],
    can_manage: true,
    ...overrides,
  };
}

describe('Programs and curricula', () => {
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

  it('lists programs and adds one', async () => {
    const fixture = TestBed.createComponent(ProgramsPage);
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/academics/programs').flush([BSC]);
    http.expectOne((r) => r.url === '/api/v1/institution/departments').flush({ ...EMPTY, results: [{ id: 'd1', code: 'PHY', name: 'Physics', campus: null, parent: null, is_active: true, version: 1 }] });
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('B.Sc Physics');
    const set = (id: string, value: string) => (root.querySelector<HTMLInputElement>(`#${id}`)!.value = value);
    set('new-code', 'BSC-MAT');
    set('new-name', 'B.Sc Mathematics');
    set('new-qualification', 'B.Sc');
    set('new-length', '6');
    set('new-department', 'd1');
    root.querySelector<HTMLFormElement>('form')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne((r) => r.method === 'POST');
    expect(request.request.body).toEqual({ code: 'BSC-MAT', name: 'B.Sc Mathematics', qualification: 'B.Sc', length_terms: 6, department: 'd1' });
    request.flush({ ...BSC, id: 'p2', code: 'BSC-MAT' });
  });

  it('drafts a regulation from the program page', async () => {
    const fixture = TestBed.createComponent(ProgramPage);
    fixture.componentRef.setInput('id', 'p1');
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/academics/programs/p1').flush(BSC);
    http.expectOne('/api/v1/institution/academics/programs/p1/curricula').flush([curriculum({ status: 'published', status_label: 'Published' })]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('R2026 rev 1');
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    root.querySelector<HTMLInputElement>('#new-regulation')!.value = 'R2027';
    root.querySelector<HTMLInputElement>('#new-cohort')!.value = '2027';
    root.querySelector<HTMLInputElement>('#new-credits')!.value = '120';
    root.querySelector<HTMLFormElement>('form')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/academics/programs/p1/curricula');
    expect(request.request.body).toEqual({ regulation: 'R2027', cohort: 2027, credits_required: '120' });
    request.flush(curriculum({ id: 'cv2', regulation: 'R2027' }));
    expect(navigate).toHaveBeenCalledWith(['/app/academics/curricula', 'cv2']);
  });

  async function open(body: Curriculum) {
    const fixture = TestBed.createComponent(CurriculumPage);
    fixture.componentRef.setInput('id', 'cv1');
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/academics/curricula/cv1').flush(body);
    await fixture.whenStable();
    return fixture;
  }

  it('groups courses by term with their prerequisites', async () => {
    const root = (await open(curriculum())).nativeElement as HTMLElement;
    const terms = [...root.querySelectorAll('h3')].map((h) => h.textContent?.trim());
    expect(terms).toEqual(['Term 1', 'Term 3']);
    expect(root.textContent).toContain('needs PHY101');
    expect(root.textContent).toContain('8.0 of 120.0 credits');
  });

  it('adds a course to a draft with its category, term and prerequisites', async () => {
    const fixture = await open(curriculum());
    const root = fixture.nativeElement as HTMLElement;
    const component = fixture.componentInstance as unknown as { choose(id: string, label: string): void };
    component.choose('c3', 'MAT101 Calculus');
    await fixture.whenStable();
    const select = (id: string, value: string) => {
      const box = root.querySelector<HTMLSelectElement>(`#${id}`)!;
      box.value = value;
      box.dispatchEvent(new Event('change'));
    };
    select('add-category', 'elective');
    select('add-term', '2');
    root.querySelector<HTMLInputElement>('#add-group')!.value = 'Maths elective';
    const needs = root.querySelector<HTMLInputElement>('#needs-c1')!;
    needs.checked = true;
    needs.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    root.querySelector<HTMLFormElement>('#add-course')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/academics/curricula/cv1/courses');
    expect(request.request.body).toEqual({ course: 'c3', category: 'elective', term: 2, elective_group: 'Maths elective', prerequisites: ['c1'] });
    request.flush(curriculum());
    await fixture.whenStable();
    // The form is cleared after adding, and what the next add sends matches what it shows.
    component.choose('c4', 'PHY102 Waves');
    await fixture.whenStable();
    root.querySelector<HTMLFormElement>('#add-course')!.dispatchEvent(new Event('submit'));
    const next = http.expectOne('/api/v1/institution/academics/curricula/cv1/courses');
    expect(next.request.body).toEqual({ course: 'c4', category: 'core', term: 1, elective_group: '', prerequisites: [] });
  });

  it('publishes with the version it shows', async () => {
    const fixture = await open(curriculum());
    const root = fixture.nativeElement as HTMLElement;
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Publish')!.click();
    await fixture.whenStable();
    const request = http.expectOne('/api/v1/institution/academics/curricula/cv1/publish');
    expect(request.request.body).toEqual({ version: 4 });
    request.flush(curriculum({ status: 'published', status_label: 'Published', version: 5 }));
  });

  it('shows a published regulation without edit controls and offers a new revision', async () => {
    const fixture = await open(curriculum({ status: 'published', status_label: 'Published' }));
    const root = fixture.nativeElement as HTMLElement;
    const labels = [...root.querySelectorAll('button')].map((b) => b.textContent?.trim());
    expect(labels).not.toContain('Publish');
    expect(labels.some((label) => label?.startsWith('Remove'))).toBe(false);
    expect(root.querySelector('#add-course')).toBeNull();
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'New revision')!.click();
    await fixture.whenStable();
    const request = http.expectOne('/api/v1/institution/academics/curricula/cv1/revise');
    expect(request.request.body).toEqual({ version: 4 });
    request.flush(curriculum({ id: 'cv2', revision: 2 }));
    expect(navigate).toHaveBeenCalledWith(['/app/academics/curricula', 'cv2']);
  });
});
