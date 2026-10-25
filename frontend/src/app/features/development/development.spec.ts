import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { makeMe, signInAs } from '../../core/test-data';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { CareersPage } from '../student/careers-page';
import { PlacementsPage } from './placements-page';
import { SupervisionPage } from './supervision-page';

describe('Institutional development pages', () => {
  let http: HttpTestingController;

  async function as(kind: 'staff' | 'student', modules: string[]) {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    const me = makeMe();
    me.membership = { ...me.membership!, kind, modules_enabled: modules };
    await signInAs(me);
  }

  function respond(url: string, body: unknown) {
    for (const request of http.match((r) => r.url === url)) {
      request.flush(body as object);
    }
  }

  it('offers a shortlisted student from the applications list', async () => {
    await as('staff', ['placements']);
    const fixture = TestBed.createComponent(PlacementsPage);
    await fixture.whenStable();
    respond('/api/v1/development/employers', []);
    respond('/api/v1/development/placement-report', [{ opportunity: 'Summer analyst', employer: 'Infosys', kind: 'internship', applied: 3, offers: 2, accepted: 1 }]);
    respond('/api/v1/development/internships', []);
    respond('/api/v1/development/alumni', []);
    respond('/api/v1/development/opportunities', [
      { id: 'o1', title: 'Summer analyst', kind: 'internship', employer: 'Infosys', description: '', programs: [], min_cgpa: '7.50', closes_on: '2026-11-04' },
    ]); // prettier-ignore
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('2 offers · 1 accepted');
    root.querySelector<HTMLButtonElement>('[aria-label="Applications for Summer analyst"]')!.click();
    await fixture.whenStable();
    http.expectOne('/api/v1/development/opportunities/o1/applications').flush([
      { id: 'a1', opportunity: { id: 'o1', title: 'Summer analyst', employer: 'Infosys', kind: 'internship' }, state: 'shortlisted',
        created_at: '2026-10-20T00:00:00Z', student: { number: '2026-0001', name: 'Asha Rao' }, eligibility: { cgpa: '8.00', program: 'BSC', checked_on: '2026-10-20' } },
    ]); // prettier-ignore
    await fixture.whenStable();
    root.querySelector<HTMLButtonElement>('[aria-label="Offer Asha Rao"]')!.click();
    expect(http.expectOne('/api/v1/development/applications/a1/state').request.body).toEqual({ state: 'offered' });
  });

  it('asks the student to agree before applying, and shows why they cannot', async () => {
    await as('student', ['placements']);
    const dialog = TestBed.inject(ConfirmDialog);
    vi.spyOn(dialog, 'ask').mockResolvedValue(true);
    const fixture = TestBed.createComponent(CareersPage);
    await fixture.whenStable();
    respond('/api/v1/student/placements', {
      opportunities: [
        { id: 'o1', title: 'Summer analyst', kind: 'internship', employer: 'Infosys', description: '', programs: [], min_cgpa: '7.50',
          closes_on: '2026-11-04', eligibility: { eligible: false, reasons: ['Needs a CGPA of 7.50.'] } },
        { id: 'o2', title: 'Graduate engineer', kind: 'job', employer: 'Infosys', description: '', programs: [], min_cgpa: null,
          closes_on: '2026-11-04', eligibility: { eligible: true, reasons: [] } },
      ],
      applications: [], alumni: null,
    }); // prettier-ignore
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Needs a CGPA of 7.50.');
    expect(root.querySelector('[aria-label="Apply for Summer analyst"]')).toBeNull();
    root.querySelector<HTMLButtonElement>('[aria-label="Apply for Graduate engineer"]')!.click();
    await fixture.whenStable();
    expect(dialog.ask).toHaveBeenCalled();
    expect(http.expectOne('/api/v1/student/placements/o2/apply').request.body).toEqual({ consent: true });
  });

  it('uploads evidence asked of a staff member', async () => {
    await as('staff', ['quality']);
    const fixture = TestBed.createComponent(SupervisionPage);
    await fixture.whenStable();
    respond('/api/v1/development/scholars', []);
    respond('/api/v1/development/evidence', [
      { id: 'r1', cycle: { id: 'y1', framework: 'NAAC', period: '2025-26' }, criterion: '3.2.1', title: 'Papers', owner: 'Head of CS',
        state: 'requested', note: '', versions: [] },
    ]); // prettier-ignore
    await fixture.whenStable();
    http.expectNone('/api/v1/development/internships');
    const input = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('input[type=file]')!;
    Object.defineProperty(input, 'files', { value: [new File(['%PDF-1.4'], 'papers.pdf', { type: 'application/pdf' })] });
    input.dispatchEvent(new Event('change'));
    const upload = http.expectOne('/api/v1/development/evidence/r1/upload');
    expect((upload.request.body as FormData).get('file')).toBeInstanceOf(File);
  });
});
