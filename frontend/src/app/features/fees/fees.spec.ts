import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { FeeStatement, StudentRecord } from '../../core/api/types';
import { makeMe, signInAs } from '../../core/test-data';
import { FeesPage } from './fees-page';
import { FeesSection } from './fees-section';
import { PayOnline } from './pay-online';

const STATEMENT: FeeStatement = {
  student: { id: 's1', number: '2026-0001', full_name: 'Kiran Rao' }, currency: 'INR', outstanding: '3000.00', unapplied: '0.00', online: false,
  invoices: [{ id: 'i1', number: 'INV-2026-00001', issued_on: '2026-10-01', due_on: '2026-11-15', plan_revision: null,
    lines: [{ head: 'TUITION', description: 'Tuition', amount: '10000.00' }], issued_charges: '10000.00', credit_notes: '1000.00',
    net_charges: '9000.00', net_allocated: '6000.00', outstanding: '3000.00', state: 'partially_paid', credit_notes_list: [] }],
  payments: [{ id: 'p1', amount: '6000.00', channel: 'cash', state: 'succeeded', state_label: 'Received', reference: '', order_id: null,
    created_at: '2026-10-10T10:00:00Z', receipt: { number: 'RCT-2026-00001', issued_at: '2026-10-10T10:00:00Z' }, unapplied: '0.00', refunds: [] }],
}; // prettier-ignore

describe('Fees pages', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    const cashier = makeMe();
    cashier.membership = {
      ...cashier.membership!,
      modules_enabled: ['students', 'fees'],
      permissions: ['fees.read', 'fees.manage', 'fees.collect', 'fees.approve', 'fees.reconcile', 'student.read'],
    };
    await signInAs(cashier);
  });

  function respond(url: string, body: unknown) {
    for (const request of http.match((r) => r.url === url)) {
      request.flush(body as object);
    }
  }

  function fill(root: HTMLElement, values: Record<string, string>) {
    for (const [id, value] of Object.entries(values)) {
      root.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value = value;
    }
  }

  it('records a payment at the office and asks for a credit note', async () => {
    const fixture = TestBed.createComponent(FeesSection);
    fixture.componentRef.setInput('student', { id: 's1' } as StudentRecord);
    await fixture.whenStable();
    respond('/api/v1/institution/fees/students/s1/statement', STATEMENT);
    respond('/api/v1/institution/fees/heads', [{ id: 'h1', code: 'TUITION', name: 'Tuition' }]);
    respond('/api/v1/institution/fees/plans', []);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('₹3000.00 outstanding');
    fill(root, { 'pay-amount': '3000', 'pay-ref': 'Counter 1' });
    root.querySelector<HTMLFormElement>('#record-payment')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne('/api/v1/institution/fees/payments').request.body).toEqual({ student: 's1', amount: '3000', channel: 'cash', reference: 'Counter 1' });
    fill(root, { 'cn-amount': '500', 'cn-reason': 'Sibling' });
    root.querySelector<HTMLFormElement>('#credit-note')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne('/api/v1/institution/fees/credit-notes').request.body).toEqual({ invoice: 'i1', kind: 'concession', amount: '500', reason: 'Sibling' });
  });

  it('approves a credit note and sets up the test sandbox', async () => {
    const fixture = TestBed.createComponent(FeesPage);
    await fixture.whenStable();
    respond('/api/v1/institution/fees/credit-notes', [{ id: 'c1', invoice: 'INV-2026-00001', kind: 'concession', amount: '1000.00', reason: 'Sibling' }]);
    for (const url of ['refunds', 'heads', 'plans', 'cases', 'trial-balance']) {
      respond(`/api/v1/institution/fees/${url}`, []);
    }
    respond('/api/v1/institution/fees/provider', null);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Not set up: families pay at the office');
    root.querySelector<HTMLButtonElement>('[aria-label="Approve credit note on INV-2026-00001"]')!.click();
    expect(http.expectOne('/api/v1/institution/fees/credit-notes/c1/approve').request.method).toBe('POST');
    fill(root, { 'prov-merchant': 'ASTER-TEST', 'prov-secret': 'whsec' });
    root.querySelector<HTMLFormElement>('#provider')!.dispatchEvent(new Event('submit'));
    const put = http.expectOne('/api/v1/institution/fees/provider');
    expect([put.request.method, put.request.body]).toEqual(['PUT', { provider: 'sandbox', merchant_id: 'ASTER-TEST', webhook_secret: 'whsec' }]);
  });

  it('is honest about online payment', async () => {
    const fixture = TestBed.createComponent(PayOnline);
    fixture.componentRef.setInput('statement', STATEMENT);
    fixture.componentRef.setInput('orders', 'student/fees/orders');
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain("Online payment isn't set up here; pay at the office.");
    const pending = { ...STATEMENT, online: true, payments: [{ ...STATEMENT.payments[0], state: 'pending' as const, receipt: null }] };
    fixture.componentRef.setInput('statement', pending);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Confirmation pending');
    [...root.querySelectorAll('button')].find((b) => b.textContent?.includes('online'))!.click();
    expect(http.expectOne('/api/v1/student/fees/orders').request.body).toEqual({ invoice: 'i1' });
  });
});
