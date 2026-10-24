import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { ClassSessionT, ConversationT } from '../../core/api/types';
import { CallPage } from './call-page';
import { ClassPage } from './class-page';
import { ThreadPage } from './thread-page';

const THREAD: ConversationT = {
  id: 'c1', kind: 'family', subject: 'Science homework', student: { number: '2026-0001', full_name: 'Kiran Rao' },
  participants: ['Asha Rao', 'Science Teacher'], others: [{ id: 'u2', full_name: 'Science Teacher', role: 'teacher' }], unread: 0,
  last_sequence: 1, messages: [{ sequence: 1, sender: 'Asha Rao', mine: true, body: 'Hello', at: '2026-10-24T09:00:00Z' }],
}; // prettier-ignore

const CLASS: ClassSessionT = {
  id: 'k1', title: 'Revision', state: 'live', state_label: 'Live', starts_at: '2026-10-24T09:00:00Z', host: 'Science Teacher',
  target: { kind: 'section', id: 's1', label: '6A' }, recording: false, is_host: true,
  participants: [{ id: 'p1', full_name: 'Kiran Rao', role: 'attendee', admission: 'waiting', present: false, seconds: 0 }],
}; // prettier-ignore

describe('Communication pages', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { snapshot: { data: {} } } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  it('retries a failed reply with the same message id, so it is never posted twice', async () => {
    const fixture = TestBed.createComponent(ThreadPage);
    fixture.componentRef.setInput('id', 'c1');
    await fixture.whenStable();
    http.expectOne('/api/v1/communication/conversations/c1').flush(THREAD);
    await fixture.whenStable();
    http.expectOne('/api/v1/communication/conversations/c1/read').flush(null);
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLTextAreaElement>('#reply-body')!.value = 'Thank you';
    const form = root.querySelector<HTMLFormElement>('#reply')!;
    form.dispatchEvent(new Event('submit'));
    const first = http.expectOne('/api/v1/communication/conversations/c1/messages');
    first.flush({ type: 'x', title: 'x', status: 503, detail: 'Try again' }, { status: 503, statusText: 'Unavailable' });
    form.dispatchEvent(new Event('submit'));
    const second = http.expectOne('/api/v1/communication/conversations/c1/messages');
    expect(second.request.body.client_id).toBe(first.request.body.client_id);
    expect(second.request.body.body).toBe('Thank you');
  });

  it('lets the teacher in a waiting student', async () => {
    const fixture = TestBed.createComponent(ClassPage);
    fixture.componentRef.setInput('id', 'k1');
    await fixture.whenStable();
    http.expectOne('/api/v1/communication/classes/k1').flush(CLASS);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('recording off');
    root.querySelector<HTMLButtonElement>('[aria-label="Let Kiran Rao in"]')!.click();
    expect(http.expectOne('/api/v1/communication/classes/k1/participants/p1/admit').request.method).toBe('POST');
  });

  it('tells a student they are waiting to be let in', async () => {
    const fixture = TestBed.createComponent(ClassPage);
    fixture.componentRef.setInput('id', 'k1');
    await fixture.whenStable();
    http.expectOne('/api/v1/communication/classes/k1').flush({ ...CLASS, is_host: false, participants: undefined });
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Join')!.click();
    http.expectOne('/api/v1/communication/classes/k1/join').flush({ admission: 'waiting', token: null, session: { ...CLASS, is_host: false } });
    await fixture.whenStable();
    expect(root.textContent).toContain('Waiting for the teacher to let you in.');
  });

  it('answers a ringing call and says when no provider is set up', async () => {
    const fixture = TestBed.createComponent(CallPage);
    fixture.componentRef.setInput('id', 'k9');
    await fixture.whenStable();
    http.expectOne('/api/v1/communication/calls/k9').flush({ id: 'k9', state: 'ringing', state_label: 'Ringing', reason: '', caller: 'Teacher', callee: 'Asha', token: null });
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Answer')!.click();
    http.expectOne('/api/v1/communication/calls/k9/accept').flush(
      { type: 'x', title: 'x', status: 409, code: 'integration_not_configured', detail: 'No call provider is set up here.' },
      { status: 409, statusText: 'Conflict' },
    );
    http.expectOne('/api/v1/communication/calls/k9').flush({ id: 'k9', state: 'failed', state_label: 'Failed', reason: 'integration_not_configured', caller: 'Teacher', callee: 'Asha', token: null });
    await fixture.whenStable();
    expect(root.textContent).toContain('no call provider is set up here');
  });
});
