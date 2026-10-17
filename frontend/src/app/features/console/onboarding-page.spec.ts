import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { OnboardingPage } from './onboarding-page';

type Wizard = {
  form: OnboardingPage['form'];
  step: () => number;
  create: () => void;
};

const VALUES = {
  identity: { legal_name: 'Aster Educational Society', display_name: 'Aster School', category: 'school' },
  contacts: { contact_email: 'office@aster.example', contact_phone: '+91 90000 00001' },
  address: { slug: 'aster-school' },
  admin: { full_name: 'Asha Rao', username: 'aster-school.admin', password: 'First-pass-2026' },
};

describe('OnboardingPage', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  async function open(): Promise<Wizard> {
    const fixture = TestBed.createComponent(OnboardingPage);
    await fixture.whenStable();
    return fixture.componentInstance as unknown as Wizard;
  }

  it('suggests the address and admin login from the name until they are typed by hand', async () => {
    const wizard = await open();
    wizard.form.controls.identity.controls.display_name.setValue('Aster School, Vijayawada');
    expect(wizard.form.controls.address.controls.slug.value).toBe('aster-school-vijayawada');
    expect(wizard.form.controls.admin.controls.username.value).toBe('aster-school-vijayawada.admin');
    wizard.form.controls.address.controls.slug.setValue('aster');
    wizard.form.controls.address.controls.slug.markAsDirty();
    wizard.form.controls.identity.controls.display_name.setValue('Something Else');
    expect(wizard.form.controls.address.controls.slug.value).toBe('aster');
  });

  it('reuses one idempotency key across retries', async () => {
    const wizard = await open();
    wizard.form.patchValue(VALUES);
    wizard.create();
    const first = http.expectOne('/api/v1/platform/institutions');
    const key = first.request.headers.get('Idempotency-Key');
    expect(key).toMatch(/^[0-9a-f-]{36}$/);
    expect(first.request.body.admin.password).toBe('First-pass-2026');
    first.flush(null, { status: 503, statusText: 'Unavailable' });
    wizard.create();
    expect(http.expectOne('/api/v1/platform/institutions').request.headers.get('Idempotency-Key')).toBe(key);
  });

  it('jumps to the admin step on a login ID error', async () => {
    const wizard = await open();
    wizard.form.patchValue(VALUES);
    wizard.create();
    http.expectOne('/api/v1/platform/institutions').flush(
      {
        code: 'validation_failed',
        errors: [{ field: 'admin.username', code: 'invalid', message: 'This login ID is already in use.' }],
      },
      { status: 422, statusText: 'Unprocessable' },
    );
    expect(wizard.step()).toBe(3);
  });

  it('opens the new institution on its branding tab', async () => {
    const wizard = await open();
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    wizard.form.patchValue(VALUES);
    wizard.create();
    http.expectOne('/api/v1/platform/institutions').flush({ id: 'new-id' }, { status: 201, statusText: 'Created' });
    expect(navigate).toHaveBeenCalledWith('/console/institutions/new-id?tab=branding');
  });
});
