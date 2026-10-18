import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { StaffApplication } from '../../core/api/types';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { ApplicationReviewPage } from './application-review-page';
import { CycleEditorPage } from './cycle-editor-page';

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

  it('asks for a first password to enroll', async () => {
    const fixture = await review(staffApplication({ stage: 'accepted', stage_label: 'Offer accepted', actions: ['enroll'] }));
    answers.push('Welcome-2027-pass');
    button(fixture.nativeElement, 'Enroll')!.click();
    await fixture.whenStable();
    const request = http.expectOne('/api/v1/institution/admissions/applications/a1/enroll');
    expect(request.request.body).toEqual({ version: 5, password: 'Welcome-2027-pass' });
  });
});
