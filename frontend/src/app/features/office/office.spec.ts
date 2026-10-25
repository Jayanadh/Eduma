import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { makeMe, signInAs } from '../../core/test-data';
import { BookingsPage } from './bookings-page';
import { LeavePage } from './leave-page';
import { PayrollPage } from './payroll-page';
import { PurchasingPage } from './purchasing-page';
import { StaffOfficePage } from './staff-office-page';

describe('Staff services pages', () => {
  let http: HttpTestingController;

  async function holding(...permissions: string[]) {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    const me = makeMe();
    me.membership = { ...me.membership!, permissions: ['institution.read', ...permissions] };
    await signInAs(me);
  }

  function respond(url: string, body: unknown) {
    for (const request of http.match((r) => r.url === url)) {
      request.flush(body as object);
    }
  }

  const leave = (state: string, name = 'Kavya Nair') => ({
    id: `l-${state}`, employee: { id: 'e1', number: 'AST-101', name }, leave_type: { id: 'k1', code: 'CL', name: 'Casual leave', paid: true },
    starts_on: '2026-11-02', ends_on: '2026-11-03', days: 2, reason: 'Family function', state, decided_by: null,
  }); // prettier-ignore

  it('asks for leave, cancels it, and lets an approver decide someone else’s', async () => {
    await holding('hr.leave_approve');
    const fixture = TestBed.createComponent(LeavePage);
    await fixture.whenStable();
    respond('/api/v1/institution/hr/leave-types', [{ id: 'k1', code: 'CL', name: 'Casual leave', days_per_year: 12, paid: true }]);
    for (const request of http.match((r) => r.url === '/api/v1/institution/hr/leave')) {
      const all = request.request.params.get('all');
      request.flush(all ? { requests: [leave('submitted', 'Arjun Das')], balances: [] } : {
        requests: [leave('approved')], balances: [{ code: 'CL', name: 'Casual leave', entitled: 12, taken: 2, waiting: 0, left: 10 }],
      }); // prettier-ignore
    }
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('10 of 12 days left');
    root.querySelector<HTMLInputElement>('#leave-from')!.value = '2026-12-01';
    root.querySelector<HTMLInputElement>('#leave-to')!.value = '2026-12-02';
    root.querySelector<HTMLInputElement>('#leave-reason')!.value = 'Wedding';
    root.querySelector<HTMLFormElement>('#ask-leave')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne((r) => r.method === 'POST' && r.url === '/api/v1/institution/hr/leave').request.body).toEqual({
      leave_type: 'k1', starts_on: '2026-12-01', ends_on: '2026-12-02', reason: 'Wedding',
    }); // prettier-ignore
    root.querySelector<HTMLButtonElement>('[aria-label="Approve leave for Arjun Das"]')!.click();
    expect(http.expectOne('/api/v1/institution/hr/leave/l-submitted/approve').request.method).toBe('POST');
    expect(root.querySelector('[aria-label^="Cancel leave"]')).not.toBeNull();
  });

  it('records staff attendance only for people given a mark', async () => {
    await holding('hr.manage');
    const fixture = TestBed.createComponent(StaffOfficePage);
    await fixture.whenStable();
    respond('/api/v1/institution/hr/leave-types', []);
    for (const request of http.match((r) => r.url === '/api/v1/institution/hr/attendance')) {
      request.flush([
        { id: 'e1', number: 'AST-101', name: 'Kavya Nair', status: 'on_leave' },
        { id: 'e2', number: 'AST-102', name: 'Arjun Das', status: null },
        { id: 'e3', number: 'AST-103', name: 'Leela Menon', status: null },
      ]);
    }
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('On leave');
    root.querySelector<HTMLSelectElement>('#mark-e2')!.value = 'present';
    root.querySelector<HTMLButtonElement>('#save-attendance')!.click();
    const body = http.expectOne((r) => r.method === 'POST').request.body;
    expect(body.marks).toEqual([{ employee: 'e2', status: 'present' }]);
  });

  it('shows the approver only the approval step, and no pay', async () => {
    await holding('payroll.approve');
    const fixture = TestBed.createComponent(PayrollPage);
    await fixture.whenStable();
    respond('/api/v1/institution/hr/payroll', [
      { id: 'c1', month: '2026-03-01', state: 'validated', prepared_by: 'Rahul Shah', approved_by: null, exported_at: null, people: 1, net: '54200.00' },
    ]); // prettier-ignore
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    http.expectNone('/api/v1/institution/hr/employees');
    expect(root.querySelector('#set-pay')).toBeNull();
    expect(root.querySelector('[aria-label^="Validate"]')).toBeNull();
    root.querySelector<HTMLButtonElement>('[aria-label^="Approve"]')!.click();
    expect(http.expectOne('/api/v1/institution/hr/payroll/c1/approve').request.method).toBe('POST');
  });

  it('receives what is still to come on an order', async () => {
    await holding('procurement.manage');
    const fixture = TestBed.createComponent(PurchasingPage);
    await fixture.whenStable();
    respond('/api/v1/institution/stores/rules', [{ revision: 1, single_approval_limit: '50000.00', published_at: '2026-10-01T00:00:00Z' }]);
    respond('/api/v1/institution/stores/items', []);
    respond('/api/v1/institution/stores/suppliers', []);
    respond('/api/v1/institution/stores/requisitions', [
      { id: 'r1', title: 'Biology lab', state: 'partially_received', total: '15000.00', rule_revision: 1, approvals_needed: 1,
        approvals: ['Dr. Iyer'], requested_by: 'Stores', supplier: 'Lab Supplies Co',
        lines: [{ id: 'x1', item: { id: 'i1', code: 'MIC-01', name: 'Microscope', unit: 'each' }, quantity: '10.00', unit_cost: '1500.00', received: '6.00' }] },
    ]); // prettier-ignore
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('1 of 1 approvals (rule 1)');
    expect(root.querySelector('[aria-label="Approve Biology lab"]')).toBeNull();
    root.querySelector<HTMLButtonElement>('[aria-label="Receive the rest of Biology lab"]')!.click();
    expect(http.expectOne('/api/v1/institution/stores/requisitions/r1/receive').request.body).toEqual({ lines: [{ line: 'x1', quantity: '4.00' }] });
  });

  it('books a lab and cancels only your own bookings', async () => {
    await holding();
    const fixture = TestBed.createComponent(BookingsPage);
    await fixture.whenStable();
    respond('/api/v1/institution/stores/assets', [
      { id: 'a1', tag: 'LAB-PHY-1', name: 'Physics lab', category: 'Laboratory', location: '', custodian: null, bookable: true, status: 'in_use', disposal_reason: '' },
    ]); // prettier-ignore
    const slot = (id: string, mine: boolean, by: string) => ({
      id, asset: { id: 'a1', tag: 'LAB-PHY-1', name: 'Physics lab' }, starts_at: '2026-11-02T04:00:00Z', ends_at: '2026-11-02T06:00:00Z',
      purpose: 'Practical', booked_by: by, canceled: false, mine,
    }); // prettier-ignore
    respond('/api/v1/institution/stores/bookings', [slot('b1', true, 'Asha Rao'), slot('b2', false, 'Arjun Das')]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelectorAll('[aria-label="Cancel booking of Physics lab"]').length).toBe(1);
    root.querySelector<HTMLInputElement>('#book-from')!.value = '2026-11-03T09:00';
    root.querySelector<HTMLInputElement>('#book-to')!.value = '2026-11-03T11:00';
    root.querySelector<HTMLInputElement>('#book-purpose')!.value = 'Optics practical';
    root.querySelector<HTMLFormElement>('#book')!.dispatchEvent(new Event('submit'));
    const body = http.expectOne((r) => r.method === 'POST').request.body;
    expect(body.asset).toBe('a1');
    expect(new Date(body.ends_at).getTime() - new Date(body.starts_at).getTime()).toBe(2 * 3600 * 1000);
  });
});
