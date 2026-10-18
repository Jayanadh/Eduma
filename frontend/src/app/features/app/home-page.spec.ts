import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { InstitutionDetail, ReadinessItem } from '../../core/api/types';
import { makeMe, signInAs } from '../../core/test-data';
import { HomePage } from './home-page';

function institution(readiness: ReadinessItem[], status: InstitutionDetail['lifecycle_status']): InstitutionDetail {
  return {
    id: 'i1',
    slug: 'vector',
    custom_domain: '',
    modules: [],
    modules_enabled: [],
    academic_year: { label: '2026–27', starts_on: '2026-06-01', ends_on: '2027-05-31' },
    legal_name: 'Vector Society',
    display_name: 'Vector Engineering College',
    category: 'engineering_college',
    country_code: 'IN',
    timezone: 'Asia/Kolkata',
    base_currency: 'INR',
    contact_email: 'office@vector.example',
    contact_phone: '+91 90000 00003',
    address: '',
    board_affiliation_code: '',
    udise_code: '',
    aishe_code: '',
    url: 'http://vector.localhost:4201',
    lifecycle_status: status,
    status_reason: '',
    activated_at: null,
    created_at: '2026-10-17T00:00:00Z',
    version: 1,
    readiness,
  };
}

const ADMIN = { code: 'admin_ready', label: 'Institution Admin has signed in and changed their first password', done: true };
const SITE = { code: 'site_published', label: 'Public page is published', done: false };
const CONTACTS = { code: 'contacts', label: 'Contact email and phone are filled in', done: true };

describe('HomePage', () => {
  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    await signInAs(makeMe());
  });

  async function render(detail: InstitutionDetail) {
    const fixture = TestBed.createComponent(HomePage);
    await fixture.whenStable();
    TestBed.inject(HttpTestingController).expectOne('/api/v1/institution').flush(detail);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('links an unpublished page to the editor', async () => {
    const page = await render(institution([ADMIN, SITE, CONTACTS], 'setup'));
    const link = page.querySelector('a[href="/app/site"]');
    expect(link?.textContent).toContain('Public page is published');
    expect(page.textContent).not.toContain('Activation is done by the Eduma team');
  });

  it('says who activates once everything is ready', async () => {
    const page = await render(institution([ADMIN, { ...SITE, done: true }, CONTACTS], 'setup'));
    expect(page.textContent).toContain('Activation is done by the Eduma team');
  });

  it('shows the public address', async () => {
    const page = await render(institution([ADMIN, SITE, CONTACTS], 'active'));
    expect(page.textContent).toContain('http://vector.localhost:4201');
  });

  it('lists the modules in the plan honestly', async () => {
    const page = await render({ ...institution([ADMIN, SITE, CONTACTS], 'active'), modules: ['fees', 'students'] });
    expect(page.textContent).toContain('Students and guardians');
    expect(page.textContent).toContain('Fees');
    expect(page.textContent).toContain('each arrives in a later release');
  });

  it('tells a member with no role whom to ask, without the setup checklist', async () => {
    const noRole = { kind: 'staff' as const, roles: [], permissions: ['institution.read'], restricted: false, status_reason: '' };
    await signInAs(makeMe({ membership: noRole }));
    const page = await render(institution([ADMIN, SITE, CONTACTS], 'active'));
    expect(page.textContent).toContain('You have no role here yet. Ask your Institution Admin.');
    expect(page.textContent).not.toContain('Public page is published');
  });

  it('shows what waits for the viewer, which modules are on, and the academic year', async () => {
    const fixture = TestBed.createComponent(HomePage);
    await fixture.whenStable();
    const http = TestBed.inject(HttpTestingController);
    const detail = { ...institution([ADMIN, SITE, CONTACTS], 'active'), modules: ['admissions', 'students', 'fees'] };
    http.expectOne('/api/v1/institution').flush({ ...detail, modules_enabled: ['admissions', 'students'] });
    http.expectOne('/api/v1/institution/approvals').flush({
      roles: [
        {
          staff_id: 'm1',
          assignment_id: 'a1',
          person: 'Ravi Kumar',
          role_label: 'Campus Admin',
          scope_label: 'City campus',
          requested_by_name: 'Aster City Campus Admin',
          requested_at: '2026-10-19T04:00:00Z',
        },
      ],
      settings: [],
    });
    await fixture.whenStable();
    const page = fixture.nativeElement as HTMLElement;
    expect(page.textContent).toContain('Waiting for your approval');
    expect(page.querySelector('a[href="/app/staff/m1"]')?.textContent).toContain('Ravi Kumar');
    expect(page.textContent).toContain('Academic year 2026–27 (01 Jun 2026 – 31 May 2027)');
    const on = [...page.querySelectorAll('.module.on')].map((item) => item.textContent?.replace(/\s+/g, ' ').trim());
    expect(on).toEqual(['Switched on: Admissions and enrollment', 'Switched on: Students and guardians']);
  });

  it('shows no approvals card when nothing waits', async () => {
    const fixture = TestBed.createComponent(HomePage);
    await fixture.whenStable();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/institution').flush(institution([ADMIN, SITE, CONTACTS], 'active'));
    http.expectOne('/api/v1/institution/approvals').flush({ roles: [], settings: [] });
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Waiting for your approval');
  });
});
