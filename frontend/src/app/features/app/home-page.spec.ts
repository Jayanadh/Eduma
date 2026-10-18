import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { InstitutionDetail, ReadinessItem } from '../../core/api/types';
import { HomePage } from './home-page';

function institution(readiness: ReadinessItem[], status: InstitutionDetail['lifecycle_status']): InstitutionDetail {
  return {
    id: 'i1',
    slug: 'vector',
    custom_domain: '',
    modules: [],
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
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
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
});
