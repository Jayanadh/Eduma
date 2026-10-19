import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ApplicantApplication } from '../../core/api/types';
import { ApplicationFormPage } from './application-form-page';

function application(overrides: Partial<ApplicantApplication> = {}): ApplicantApplication {
  return {
    id: 'a1',
    number: '',
    stage: 'draft',
    stage_label: 'Draft',
    version: 2,
    cycle: { id: 'c1', name: 'Admissions 2027', academic_year: '2027–28', closes_on: '2026-12-17' },
    place: { id: 'p1', label: 'Class 1', campus_name: 'Main campus' },
    questions: [{ code: 'LANG', label: 'Home language', help: '', kind: 'text', options: [], required: true }],
    requirements: [{ code: 'BIRTH', label: 'Birth certificate', help: '', required: true }],
    learner_name: '',
    date_of_birth: null,
    guardian_name: '',
    guardian_relationship: '',
    guardian_phone: '',
    guardian_email: '',
    address: '',
    previous_school: '',
    answers: {},
    information_request: '',
    decision_reason: '',
    offer_expires_on: null,
    submitted_at: null,
    documents: [],
    missing: { learner_name: 'Fill this in.', 'documents.BIRTH': 'Upload the birth certificate.' },
    allowed_actions: ['edit', 'upload', 'submit', 'withdraw'],
    ...overrides,
  };
}

describe('ApplicationFormPage', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  async function open(body: ApplicantApplication) {
    const fixture = TestBed.createComponent(ApplicationFormPage);
    fixture.componentRef.setInput('id', 'a1');
    await fixture.whenStable();
    http.expectOne('/api/v1/applicant/applications/a1').flush(body);
    await fixture.whenStable();
    return fixture;
  }

  function button(root: HTMLElement, text: string) {
    return [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  }

  it('saves with the version it started from and lists what is still missing', async () => {
    const fixture = await open(application());
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Upload the birth certificate.');
    const name = root.querySelector<HTMLInputElement>('#learner-name')!;
    name.value = 'Meera Rao';
    name.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    expect(button(root, 'Submit application')!.disabled).toBe(true);
    button(root, 'Save')!.click();
    const request = http.expectOne('/api/v1/applicant/applications/a1');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body.version).toBe(2);
    expect(request.request.body.learner_name).toBe('Meera Rao');
  });

  it('uploads a document with its requirement', async () => {
    const fixture = await open(application());
    const root = fixture.nativeElement as HTMLElement;
    const input = root.querySelector<HTMLInputElement>('#doc-BIRTH')!;
    const file = new File(['%PDF-1.4'], 'birth.pdf', { type: 'application/pdf' });
    Object.defineProperty(input, 'files', { value: [file] });
    input.dispatchEvent(new Event('change'));
    const request = http.expectOne('/api/v1/applicant/applications/a1/documents');
    const form = request.request.body as FormData;
    expect(form.get('requirement')).toBe('BIRTH');
    expect((form.get('file') as File).name).toBe('birth.pdf');
  });

  it('offers to accept a place before it expires', async () => {
    const offered = application({
      stage: 'offered',
      stage_label: 'Place offered',
      number: 'A2027-0001',
      offer_expires_on: '2026-11-01',
      missing: {},
      allowed_actions: ['withdraw', 'accept'],
    });
    const fixture = await open(offered);
    const root = fixture.nativeElement as HTMLElement;
    expect(button(root, 'Accept the offer')).toBeDefined();
    expect(root.textContent).toContain('01 Nov 2026');
    expect(root.querySelector('#learner-name')).toBeNull();
  });

  it('shows what the school asked for and reopens the form', async () => {
    const asked = application({
      stage: 'needs_information',
      stage_label: 'More information needed',
      number: 'A2027-0001',
      information_request: 'Please upload a clearer photo.',
    });
    const fixture = await open(asked);
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Please upload a clearer photo.');
    expect(root.querySelector('#learner-name')).not.toBeNull();
  });

  it('keeps unsaved answers when a document is uploaded', async () => {
    const fixture = await open(application());
    const root = fixture.nativeElement as HTMLElement;
    const name = root.querySelector<HTMLInputElement>('#learner-name')!;
    name.value = 'Meera Rao';
    name.dispatchEvent(new Event('input'));
    const input = root.querySelector<HTMLInputElement>('#doc-BIRTH')!;
    Object.defineProperty(input, 'files', { value: [new File(['%PDF-1.4'], 'birth.pdf', { type: 'application/pdf' })] });
    input.dispatchEvent(new Event('change'));
    const uploaded = application({
      version: 3,
      documents: [
        {
          id: 'd1',
          requirement: 'BIRTH',
          label: 'Birth certificate',
          original_name: 'birth.pdf',
          content_type: 'application/pdf',
          size: 8,
          status: 'pending',
          uploaded_at: '2026-10-19T10:00:00Z',
        },
      ],
      missing: { learner_name: "Enter the learner's full name." },
    });
    http.expectOne('/api/v1/applicant/applications/a1/documents').flush(uploaded);
    await fixture.whenStable();
    expect(root.querySelector<HTMLInputElement>('#learner-name')!.value).toBe('Meera Rao');
    expect(root.textContent).toContain('Save your changes first.');
    button(root, 'Save')!.click();
    const save = http.expectOne('/api/v1/applicant/applications/a1');
    expect(save.request.body.version).toBe(3);
    expect(save.request.body.learner_name).toBe('Meera Rao');
  });

  it('lists every missing item even when two read the same', async () => {
    const fixture = await open(application({ missing: { a: 'Answer this.', b: 'Answer this.' } }));
    const items = (fixture.nativeElement as HTMLElement).querySelectorAll('.notice-warning li');
    expect(items.length).toBe(2);
  });
});
