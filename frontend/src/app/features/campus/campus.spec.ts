import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { StudentCampusPage } from '../student/campus-page';
import { HostelPage } from './hostel-page';
import { LibraryPage } from './library-page';

describe('Campus pages', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  function respond(url: string, body: unknown) {
    for (const request of http.match((r) => r.url === url)) {
      request.flush(body as object);
    }
  }

  it('issues a copy to a student found by number, and returns a loan', async () => {
    const fixture = TestBed.createComponent(LibraryPage);
    await fixture.whenStable();
    respond('/api/v1/institution/campus/titles', []);
    respond('/api/v1/institution/campus/loans', [
      { id: 'l1', title: 'Wings of Fire', accession: 'WF-1', borrower: 'Asha Rao', issued_on: '2026-10-20', due_on: '2026-11-03',
        returned_on: null, renewals: 0, status: 'active', fines: [] },
    ]); // prettier-ignore
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLInputElement>('#issue-accession')!.value = 'WF-2';
    root.querySelector<HTMLInputElement>('#issue-student')!.value = '2026-0002';
    root.querySelector<HTMLFormElement>('#issue')!.dispatchEvent(new Event('submit'));
    http.expectOne((r) => r.url === '/api/v1/institution/students').flush({ count: 1, next: null, previous: null, results: [{ id: 's2', number: '2026-0002' }] });
    expect(http.expectOne((r) => r.method === 'POST').request.body).toEqual({ accession: 'WF-2', student: 's2' });
    root.querySelector<HTMLButtonElement>('[aria-label="Return WF-1"]')!.click();
    expect(http.expectOne('/api/v1/institution/campus/loans/l1/return').request.method).toBe('POST');
  });

  it('approves a request into a free bed and an out-pass', async () => {
    const fixture = TestBed.createComponent(HostelPage);
    await fixture.whenStable();
    respond('/api/v1/institution/campus/hostels', [
      { id: 'h1', name: 'Girls', occupied: 0, capacity: 1, beds: [{ id: 'b1', room: '101', label: 'A', resident: null }] },
    ]);
    respond('/api/v1/institution/campus/allocations', [
      { id: 'a1', student: { number: '2026-0001', full_name: 'Asha Rao' }, bed: null, starts_on: '2026-06-01', ends_on: '2027-03-31', state: 'requested' },
    ]);
    respond('/api/v1/institution/campus/out-passes', [
      { id: 'o1', student: 'Meera Iyer', leaves_at: '2026-11-01T10:00:00Z', returns_at: '2026-11-02T18:00:00Z', reason: 'Family visit', state: 'requested' },
    ]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLButtonElement>('[aria-label="Approve Asha Rao"]')!.click();
    expect(http.expectOne('/api/v1/institution/campus/allocations/a1/approve').request.body).toEqual({ bed: 'b1' });
    root.querySelector<HTMLButtonElement>('[aria-label="Approve out-pass for Meera Iyer"]')!.click();
    expect(http.expectOne('/api/v1/institution/campus/out-passes/o1/approve').request.method).toBe('POST');
  });

  it('lets a resident ask for an out-pass', async () => {
    const fixture = TestBed.createComponent(StudentCampusPage);
    await fixture.whenStable();
    respond('/api/v1/student/campus', {
      loans: [], transport: null, out_passes: [],
      hostel: { id: 'a1', bed: '101 A', state: 'allocated', starts_on: '2026-06-01', ends_on: '2027-03-31' },
    }); // prettier-ignore
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLInputElement>('#out-leaves')!.value = '2026-11-01T10:00';
    root.querySelector<HTMLInputElement>('#out-returns')!.value = '2026-11-02T18:00';
    root.querySelector<HTMLInputElement>('#out-reason')!.value = 'Family visit';
    root.querySelector<HTMLFormElement>('#out-pass')!.dispatchEvent(new Event('submit'));
    const body = http.expectOne('/api/v1/student/campus/out-passes').request.body;
    expect(body.reason).toBe('Family visit');
    expect(new Date(body.leaves_at).getTime()).toBeLessThan(new Date(body.returns_at).getTime());
  });
});
