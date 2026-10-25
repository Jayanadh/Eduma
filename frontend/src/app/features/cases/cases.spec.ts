import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { CasePage } from './case-page';
import { CasesPage } from './cases-page';

describe('Case pages', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  const base = {
    id: 'c1', number: 'SC-0001', case_type: 'grievance', type_label: 'Academic grievance', confidential: true,
    state: 'assigned', state_label: 'Being looked at', created_at: '2026-10-20T10:00:00Z',
  }; // prettier-ignore

  it('opens a case with only the kind, subject and description', async () => {
    const fixture = TestBed.createComponent(CasesPage);
    await fixture.whenStable();
    http.expectOne('/api/v1/service-cases/').flush([{ ...base, seen_as: 'triage', assignee: 'G One', due_at: '2026-11-04T10:00:00Z', overdue: false }]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('SC-0001 Academic grievance');  // a shell: no subject
    root.querySelector<HTMLSelectElement>('#case-type')!.value = 'service_request';
    root.querySelector<HTMLInputElement>('#case-subject')!.value = 'Bonafide certificate';
    root.querySelector<HTMLTextAreaElement>('#case-description')!.value = 'For a visa.';
    root.querySelector<HTMLFormElement>('#open-case')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne((r) => r.method === 'POST').request.body).toEqual({
      case_type: 'service_request', subject: 'Bonafide certificate', description: 'For a visa.',
    }); // prettier-ignore
  });

  it('lets the officer write an internal note and resolve', async () => {
    const fixture = TestBed.createComponent(CasePage);
    fixture.componentRef.setInput('id', 'c1');
    await fixture.whenStable();
    http.expectOne('/api/v1/service-cases/c1').flush({
      ...base, seen_as: 'officer', subject: 'Marks', description: 'Internal entered as 12.', requester: 'Asha Rao', notes: [],
      resolutions: [], appeal: null, can_appeal: false,
    }); // prettier-ignore
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLTextAreaElement>('#note-text')!.value = 'Asked the exam cell.';
    root.querySelector<HTMLInputElement>('#note-internal')!.checked = true;
    root.querySelector<HTMLFormElement>('#note')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne('/api/v1/service-cases/c1/notes').request.body).toEqual({ text: 'Asked the exam cell.', visibility: 'internal' });
    root.querySelector<HTMLTextAreaElement>('#resolution')!.value = 'Corrected to 22.';
    root.querySelector<HTMLFormElement>('#resolve')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne('/api/v1/service-cases/c1/resolve').request.body).toEqual({ text: 'Corrected to 22.' });
  });

  it('gives the requester no internal-note box, and an appeal once resolved', async () => {
    const fixture = TestBed.createComponent(CasePage);
    fixture.componentRef.setInput('id', 'c1');
    await fixture.whenStable();
    http.expectOne('/api/v1/service-cases/c1').flush({
      ...base, state: 'resolved', seen_as: 'requester', subject: 'Marks', description: 'x', notes: [],
      resolutions: [{ stage: 'original', text: 'Corrected to 22.', at: '2026-10-22T10:00:00Z' }], appeal: null, can_appeal: true,
    }); // prettier-ignore
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('#note-internal')).toBeNull();
    root.querySelector<HTMLTextAreaElement>('#appeal-reason')!.value = 'Final mark not recalculated.';
    root.querySelector<HTMLFormElement>('#appeal')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne('/api/v1/service-cases/c1/appeals').request.body).toEqual({ reason: 'Final mark not recalculated.' });
  });
});
