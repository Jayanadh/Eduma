import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter, Router } from '@angular/router';
import { AffiliationGrant, SubmissionBatch } from '../../core/api/types';
import { makeMe, signInAs } from '../../core/test-data';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { AffiliationsPage } from '../console/affiliations-page';
import { InstitutionAffiliationsPage } from './affiliations-page';
import { BatchPage } from './batch-page';

const EMPTY = { count: 0, next: null, previous: null, results: [] };
const GRANT: AffiliationGrant = {
  id: 'g1', version: 1, college: { id: 'c1', name: 'Meridian College' }, university: { id: 'u1', name: 'Summit University' },
  purpose: 'Central examination', categories: ['identity'], actions: ['submit_result_batches'], starts_on: '2026-09-24',
  ends_on: '2027-09-24', evidence: 'Order 12', status: 'proposed', status_label: 'Waiting for the college’s approval',
  in_effect: false, revoked_reason: '', side: 'college',
}; // prettier-ignore

function batch(overrides: Partial<SubmissionBatch> = {}): SubmissionBatch {
  return {
    id: 'b1', reference: 'ref', revision: 1, program: 'BSC-PHY', term: '2026–27 Semester 1', status: 'draft', status_label: 'Draft',
    college: 'Meridian College', university: 'Summit University', grant: 'g1', submitted_at: null,
    rows: [
      { id: 'r1', number: '2026-0001', full_name: 'Ananya Demo', program: 'BSC-PHY', regulation: 'BSC-PHY R2026 rev 1',
        attempts: [{ course: 'PHY101', title: 'Mechanics', credits: '4.0', attempt_no: 1, outcome: 'passed', grade_point: '8.00' }],
        problems: [], is_correction: false, status: 'pending', status_label: 'Waiting for review', reason: '', current: false },
    ],
    ...overrides,
  }; // prettier-ignore
}

describe('Affiliations', () => {
  let http: HttpTestingController;
  let review = false;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ConfirmDialog, useValue: { ask: () => Promise.resolve(true), prompt: () => Promise.resolve('Grade point differs') } },
        { provide: ActivatedRoute, useFactory: () => ({ snapshot: { data: { review } } }) },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    const admin = makeMe();
    admin.membership = { ...admin.membership!, category: 'college', permissions: ['affiliation.submit', 'affiliation.review'] };
    await signInAs(admin);
  });

  function respond(url: string, body: unknown) {
    for (const request of http.match((r) => r.url === url)) {
      request.flush(body as object);
    }
  }

  it('proposes an affiliation from the console', async () => {
    const fixture = TestBed.createComponent(AffiliationsPage);
    await fixture.whenStable();
    respond('/api/v1/platform/affiliations', []);
    respond('/api/v1/platform/institutions', {
      ...EMPTY,
      results: [
        { id: 'c1', display_name: 'Meridian College', category: 'college' },
        { id: 'u1', display_name: 'Summit University', category: 'university' },
      ],
    });
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    const set = (id: string, value: string) => (root.querySelector<HTMLInputElement>(`#${id}`)!.value = value);
    set('grant-starts', '2026-10-01');
    set('grant-ends', '2027-09-30');
    set('grant-purpose', 'Central examination');
    set('grant-evidence', 'Order 12');
    root.querySelector<HTMLFormElement>('#propose')!.dispatchEvent(new Event('submit'));
    expect(http.expectOne((r) => r.method === 'POST').request.body).toEqual({
      college: 'c1', university: 'u1', purpose: 'Central examination', starts_on: '2026-10-01', ends_on: '2027-09-30', evidence: 'Order 12',
    }); // prettier-ignore
  });

  it('lets the college approve a proposed grant', async () => {
    const fixture = TestBed.createComponent(InstitutionAffiliationsPage);
    await fixture.whenStable();
    respond('/api/v1/institution/affiliations', [GRANT]);
    respond('/api/v1/institution/academics/programs', []);
    respond('/api/v1/institution/academics/years', []);
    respond('/api/v1/institution/affiliations/sent', []);
    respond('/api/v1/institution/affiliations/received', []);
    await fixture.whenStable();
    [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Approve')!.click();
    expect(http.expectOne('/api/v1/institution/affiliations/g1/approve').request.body).toEqual({ version: 1 });
  });

  it('submits a draft batch and corrects a reviewed one', async () => {
    review = false;
    const fixture = TestBed.createComponent(BatchPage);
    fixture.componentRef.setInput('id', 'b1');
    await fixture.whenStable();
    respond('/api/v1/institution/affiliations/batches/b1', batch());
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('exactly what Summit University will receive');
    [...root.querySelectorAll('button')].find((b) => b.textContent?.includes('Submit to'))!.click();
    const sent = http.expectOne('/api/v1/institution/affiliations/batches/b1/submit');
    const reviewed = batch({ status: 'reviewed', status_label: 'Reviewed' });
    reviewed.rows[0] = { ...reviewed.rows[0], status: 'accepted', status_label: 'Accepted' };
    sent.flush(reviewed);
    await fixture.whenStable();
    const box = root.querySelector<HTMLInputElement>('#correct-r1')!;
    box.checked = true;
    box.dispatchEvent(new Event('change'));
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    [...root.querySelectorAll('button')].find((b) => b.textContent?.includes('Correct and resubmit'))!.click();
    expect(http.expectOne('/api/v1/institution/affiliations/batches/b1/revise').request.body).toEqual({ corrections: ['r1'] });
  });

  it('returns a row with a reason when reviewing', async () => {
    review = true;
    const fixture = TestBed.createComponent(BatchPage);
    fixture.componentRef.setInput('id', 'b1');
    await fixture.whenStable();
    respond('/api/v1/institution/affiliations/received/b1', batch({ status: 'submitted', status_label: 'Submitted' }));
    await fixture.whenStable();
    (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('[aria-label="Return 2026-0001"]')!.click();
    await fixture.whenStable();
    expect(http.expectOne('/api/v1/institution/affiliations/received/b1/rows/r1').request.body).toEqual({
      decision: 'rejected',
      reason: 'Grade point differs',
    });
  });
});
