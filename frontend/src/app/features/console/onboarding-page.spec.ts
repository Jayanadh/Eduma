import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { defaultsFor, tick } from '../../core/modules';
import { MODULE_CATALOGUE } from '../../core/test-data';
import { OnboardingPage } from './onboarding-page';

type Wizard = {
  form: OnboardingPage['form'];
  step: () => number;
  create: () => void;
  modules: () => string[];
  chooseModules: (keys: string[]) => void;
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

  it('suggests a login ID that fits the 40-character limit for long names', async () => {
    const wizard = await open();
    wizard.form.controls.identity.controls.display_name.setValue(
      'Sri Venkateswara Institute of Technology and Management',
    );
    const username = wizard.form.controls.admin.controls.username.value;
    expect(username.length).toBeLessThanOrEqual(40);
    expect(username).toMatch(/^[a-z0-9][a-z0-9._-]{2,39}$/);
    expect(username.endsWith('.admin')).toBe(true);
    expect(username).not.toContain('-.admin');
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
    expect(wizard.step()).toBe(4);
  });

  it('opens the new institution', async () => {
    const wizard = await open();
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    wizard.form.patchValue(VALUES);
    wizard.create();
    http.expectOne('/api/v1/platform/institutions').flush({ id: 'new-id' }, { status: 201, statusText: 'Created' });
    expect(navigate).toHaveBeenCalledWith('/console/institutions/new-id');
  });

  it('starts the modules from the category defaults until they are changed by hand', async () => {
    const wizard = await open();
    http.expectOne('/api/v1/platform/modules').flush(MODULE_CATALOGUE);
    expect(wizard.modules()).toEqual(defaultsFor('school', MODULE_CATALOGUE));
    wizard.form.controls.identity.controls.category.setValue('university');
    expect(wizard.modules()).toContain('affiliations');
    wizard.chooseModules(tick(wizard.modules(), 'library', MODULE_CATALOGUE));
    wizard.form.controls.identity.controls.category.setValue('school');
    expect(wizard.modules()).toContain('affiliations');
    expect(wizard.modules()).toContain('library');
  });

  it('sends the chosen modules with the new institution', async () => {
    const wizard = await open();
    http.expectOne('/api/v1/platform/modules').flush(MODULE_CATALOGUE);
    wizard.form.patchValue(VALUES);
    wizard.chooseModules(['students']);
    wizard.create();
    expect(http.expectOne('/api/v1/platform/institutions').request.body.modules).toEqual(['students']);
  });
});
