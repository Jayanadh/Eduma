import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Enquiry } from '../../core/api/types';
import { makeMe, signInAs } from '../../core/test-data';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { EnquiriesPage } from './enquiries-page';
import { EnquiryPage } from './enquiry-page';

function enquiry(overrides: Partial<Enquiry> = {}): Enquiry {
  return {
    id: 'e1',
    version: 2,
    number: 'E2026-0001',
    contact_name: 'Ravi Kumar',
    phone: '+91 90000 11111',
    email: '',
    learner_name: 'Kiran',
    learner_date_of_birth: null,
    place: null,
    message: 'Is there a school bus to Benz Circle?',
    source: 'website',
    source_label: 'Website',
    status: 'open',
    status_label: 'Open',
    close_reason: '',
    assigned_to: null,
    next_follow_up_on: null,
    application: null,
    created_at: '2026-10-23T10:00:00Z',
    created_by: null,
    follow_ups: [],
    ...overrides,
  };
}

describe('Enquiry pages', () => {
  let http: HttpTestingController;
  let answer: string | null;

  beforeEach(() => {
    answer = 'A2027-0004';
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ConfirmDialog, useValue: { prompt: () => Promise.resolve(answer) } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  it('shows counts and sends the filters', async () => {
    const fixture = TestBed.createComponent(EnquiriesPage);
    await fixture.whenStable();
    http
      .expectOne((r) => r.url === '/api/v1/institution/admissions/enquiries')
      .flush({ count: 1, next: null, previous: null, results: [enquiry()], summary: { status: { open: 3, closed: 1 }, source: { website: 4 } } });
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('E2026-0001');
    expect(root.textContent).toContain('Open 3');
    const status = root.querySelector<HTMLSelectElement>('#enquiry-status')!;
    status.value = 'closed';
    status.dispatchEvent(new Event('change'));
    const due = root.querySelector<HTMLInputElement>('#enquiry-due')!;
    due.checked = true;
    due.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    const requests = http.match((r) => r.url === '/api/v1/institution/admissions/enquiries');
    const last = requests[requests.length - 1].request.params;
    expect(last.get('status')).toBe('closed');
    expect(last.get('due')).toBe('1');
  });

  async function open(body: Enquiry) {
    await signInAs(makeMe({ id: 'u-1' }));
    const fixture = TestBed.createComponent(EnquiryPage);
    fixture.componentRef.setInput('id', 'e1');
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/admissions/enquiries/e1').flush(body);
    for (const request of http.match(() => true)) {
      request.flush([]);
    }
    await fixture.whenStable();
    return fixture;
  }

  function button(root: HTMLElement, text: string) {
    return [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!;
  }

  it('records a follow-up with its next date', async () => {
    const fixture = await open(enquiry());
    const root = fixture.nativeElement as HTMLElement;
    const note = root.querySelector<HTMLTextAreaElement>('#follow-note')!;
    note.value = 'Called back; sending the bus routes.';
    note.dispatchEvent(new Event('input'));
    const next = root.querySelector<HTMLInputElement>('#follow-next')!;
    next.value = '2026-10-30';
    next.dispatchEvent(new Event('input'));
    root.querySelector<HTMLFormElement>('form.follow')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/admissions/enquiries/e1/follow-ups');
    expect(request.request.body).toEqual({ how: 'phone', note: 'Called back; sending the bus routes.', next_follow_up_on: '2026-10-30' });
  });

  it('assigns to me, converts by number and closes with a reason', async () => {
    const fixture = await open(enquiry());
    const root = fixture.nativeElement as HTMLElement;
    button(root, 'Assign to me').click();
    const assign = http.expectOne('/api/v1/institution/admissions/enquiries/e1');
    expect(assign.request.method).toBe('PATCH');
    expect(assign.request.body).toEqual({ version: 2, assigned_to: 'u-1' });
    assign.flush(enquiry({ version: 3, assigned_to: { id: 'u-1', full_name: 'Asha Rao' } }));
    await fixture.whenStable();
    button(root, 'Link to an application').click();
    await fixture.whenStable();
    const convert = http.expectOne('/api/v1/institution/admissions/enquiries/e1/convert');
    expect(convert.request.body).toEqual({ version: 3, application_number: 'A2027-0004' });
    convert.flush(enquiry({ version: 4 }));
    await fixture.whenStable();
    answer = 'No reply after two calls.';
    button(root, 'Close').click();
    await fixture.whenStable();
    const close = http.expectOne('/api/v1/institution/admissions/enquiries/e1/close');
    expect(close.request.body).toEqual({ version: 4, reason: 'No reply after two calls.' });
  });
});
