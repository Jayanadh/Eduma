import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { StaffApplication } from '../../core/api/types';
import { UnsavedChanges } from '../../core/unsaved-changes';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { ApplicationReviewPage } from './application-review-page';
import { CycleEditorPage } from './cycle-editor-page';
import { makeMe, signInAs } from '../../core/test-data';

const EMPTY = { count: 0, next: null, previous: null, results: [] };

function staffApplication(overrides: Partial<StaffApplication> = {}): StaffApplication {
  return {
    id: 'a1',
    number: 'A2027-0001',
    stage: 'eligible',
    stage_label: 'Eligible',
    version: 5,
    cycle: { id: 'c1', name: 'Admissions 2027', academic_year: '2027–28', closes_on: '2026-12-17' },
    place: { id: 'p1', label: 'Class 1', campus_name: 'Main campus' },
    questions: [],
    requirements: [],
    learner_name: 'Meera Rao',
    date_of_birth: '2020-05-17',
    guardian_name: 'Asha Rao',
    guardian_relationship: 'Mother',
    guardian_phone: '+91 90000 12345',
    guardian_email: '',
    address: '4 Lake Road',
    previous_school: '',
    answers: {},
    information_request: '',
    decision_reason: '',
    offer_expires_on: null,
    submitted_at: '2026-10-18T05:00:00Z',
    documents: [],
    owner: { full_name: 'Asha Rao', username: 'asha.parent' },
    decided_by_name: null,
    submissions: [],
    notes: [],
    student_id: null,
    possible_duplicates: [],
    actions: ['reject', 'offer'],
    can_review: true,
    can_approve: true,
    ...overrides,
  };
}

describe('Staff admissions pages', () => {
  let http: HttpTestingController;
  let answers: (string | null)[];

  beforeEach(() => {
    answers = [];
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ConfirmDialog,
          useValue: {
            prompt: () => Promise.resolve(answers.shift() ?? null),
            firstPassword: () => Promise.resolve(answers.shift() ?? null),
            ask: () => Promise.resolve(true),
          },
        },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  function button(root: HTMLElement, text: string) {
    return [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  }

  it('adds and removes rows and saves the lists with the cycle', async () => {
    const fixture = TestBed.createComponent(CycleEditorPage);
    await fixture.whenStable();
    for (const request of http.match(() => true)) {
      request.flush(EMPTY);
    }
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    button(root, 'Add a place')!.click();
    button(root, 'Add a place')!.click();
    await fixture.whenStable();
    expect(root.querySelectorAll('.place-row').length).toBe(2);
    button(root, 'Remove place 2')?.click();
    [...root.querySelectorAll('button')].filter((b) => b.getAttribute('aria-label') === 'Remove place 2')[0]?.click();
    await fixture.whenStable();
    expect(root.querySelectorAll('.place-row').length).toBe(1);
    button(root, 'Save cycle')!.click();
    const request = http.expectOne('/api/v1/institution/admissions/cycles');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.places.length).toBe(1);
  });

  it('will not open a cycle while it has unsaved changes', async () => {
    const draft = {
      id: 'c1',
      name: 'Admissions 2027',
      entry_year: 2027,
      academic_year: '2027–28',
      opens_on: '2026-10-18',
      closes_on: '2026-12-17',
      instructions: '',
      status: 'draft',
      version: 4,
      places: [{ code: 'C1', label: 'Class 1', campus: null, seats: 40 }],
      questions: [],
      documents: [],
      counts: {},
    };
    const fixture = TestBed.createComponent(CycleEditorPage);
    fixture.componentRef.setInput('id', 'c1');
    await fixture.whenStable();
    for (const request of http.match(() => true)) {
      request.flush(request.request.url.endsWith('/cycles/c1') ? draft : EMPTY);
    }
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(button(root, 'Open for applications')!.disabled).toBe(false);
    const name = root.querySelector<HTMLInputElement>('#cycle-name')!;
    name.value = 'Admissions 2027–28';
    name.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    expect(button(root, 'Open for applications')!.disabled).toBe(true);
    expect(root.textContent).toContain('Save your changes first.');
  });

  it('clears the leave warning before moving to a new cycle\'s page', async () => {
    const fixture = TestBed.createComponent(CycleEditorPage);
    await fixture.whenStable();
    for (const request of http.match(() => true)) {
      request.flush(EMPTY);
    }
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    const name = root.querySelector<HTMLInputElement>('#cycle-name')!;
    name.value = 'Mid-year intake';
    name.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    const unsaved = TestBed.inject(UnsavedChanges);
    expect(unsaved.dirty()).toBe(true);
    let dirtyWhenLeaving: boolean | undefined;
    vi.spyOn(TestBed.inject(Router), 'navigate').mockImplementation(() => {
      dirtyWhenLeaving = unsaved.dirty();
      return Promise.resolve(true);
    });
    button(root, 'Save cycle')!.click();
    http.expectOne('/api/v1/institution/admissions/cycles').flush({ id: 'c9' });
    expect(dirtyWhenLeaving).toBe(false);
  });

  async function review(body: StaffApplication) {
    const fixture = TestBed.createComponent(ApplicationReviewPage);
    fixture.componentRef.setInput('id', 'a1');
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/admissions/applications/a1').flush(body);
    await fixture.whenStable();
    return fixture;
  }

  it('offers only what the stage allows, and asks for an expiry date', async () => {
    const fixture = await review(staffApplication());
    const root = fixture.nativeElement as HTMLElement;
    expect(button(root, 'Mark eligible')).toBeUndefined();
    answers.push('2026-11-01');
    button(root, 'Offer a place')!.click();
    await fixture.whenStable();
    const request = http.expectOne('/api/v1/institution/admissions/applications/a1/offer');
    expect(request.request.body).toEqual({ version: 5, expires_on: '2026-11-01' });
  });

  it('warns about a possible duplicate student', async () => {
    const fixture = await review(
      staffApplication({ possible_duplicates: [{ id: 's9', number: '2027-0001', full_name: 'Arjun Demo' }] }),
    );
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Possible duplicate of 2027-0001 Arjun Demo');
  });

  it('asks for a first password to enroll', async () => {
    const fixture = await review(staffApplication({ stage: 'accepted', stage_label: 'Offer accepted', actions: ['enroll'] }));
    answers.push('Welcome-2027-pass');
    button(fixture.nativeElement, 'Enroll')!.click();
    await fixture.whenStable();
    const request = http.expectOne('/api/v1/institution/admissions/applications/a1/enroll');
    expect(request.request.body).toEqual({ version: 5, password: 'Welcome-2027-pass' });
  });

  it('lets a college place admit into a program', async () => {
    const admin = makeMe();
    admin.membership = { ...admin.membership!, category: 'college' };
    await signInAs(admin);
    const fixture = TestBed.createComponent(CycleEditorPage);
    await fixture.whenStable();
    for (const request of http.match(() => true)) {
      request.flush(request.request.url.endsWith('/academics/programs') ? [{ id: 'p1', code: 'BSC-PHY', name: 'B.Sc Physics', is_active: true }] : EMPTY);
    }
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Add a place')!.click();
    await fixture.whenStable();
    const program = root.querySelector<HTMLSelectElement>('#place-program-0')!;
    program.value = 'p1';
    program.dispatchEvent(new Event('change'));
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Save cycle')!.click();
    const request = http.expectOne('/api/v1/institution/admissions/cycles');
    expect(request.request.body.places[0].program).toBe('p1');
  });
});
