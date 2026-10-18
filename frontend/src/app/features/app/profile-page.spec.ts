import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { InstitutionDetail } from '../../core/api/types';
import { makeMe, signInAs } from '../../core/test-data';
import { ProfilePage } from './profile-page';

const ASTER = {
  id: 'i1',
  version: 3,
  legal_name: 'Aster Educational Society',
  category: 'school',
  url: 'http://aster.localhost:4201',
  contact_email: 'office@aster.example',
  contact_phone: '+91 90000 00001',
  address: '1 Lake Road',
} as InstitutionDetail;

describe('ProfilePage', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
  });

  async function render() {
    const fixture = TestBed.createComponent(ProfilePage);
    await fixture.whenStable();
    TestBed.inject(HttpTestingController).expectOne('/api/v1/institution').flush(ASTER);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('lets an admin save the office contacts', async () => {
    await signInAs(makeMe());
    const page = await render();
    expect(page.querySelector('button[type=submit]')).not.toBeNull();
    expect(page.querySelector<HTMLInputElement>('#office-email')!.disabled).toBe(false);
  });

  it('shows other members the contacts without a form they cannot save', async () => {
    const noRole = { roles: [], permissions: ['institution.read'], restricted: false, status_reason: '' };
    await signInAs(makeMe({ membership: noRole }));
    const page = await render();
    expect(page.querySelector('button[type=submit]')).toBeNull();
    expect(page.querySelector<HTMLInputElement>('#office-email')!.disabled).toBe(true);
    expect(page.textContent).toContain('Only your Institution Admin can change these.');
  });
});
