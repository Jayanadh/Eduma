import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { makeMember } from '../../core/test-data';
import { ApplyPage } from './apply-page';
import { SignupPage } from './signup-page';

const OPEN = {
  open: true,
  cycles: [
    {
      id: 'c1',
      name: 'Admissions 2027',
      academic_year: '2027–28',
      opens_on: '2026-10-18',
      closes_on: '2026-12-17',
      instructions: 'Apply before the closing date.',
      places: [{ id: 'p1', label: 'Class 1', campus_name: 'Main campus' }],
      documents: [{ code: 'BIRTH', label: 'Birth certificate', required: true }],
    },
  ],
};

describe('Apply pages', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  async function apply(body: object) {
    const fixture = TestBed.createComponent(ApplyPage);
    await fixture.whenStable();
    http.expectOne('/api/v1/public/admissions').flush(body);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('lists open cycles with their places and documents', async () => {
    const page = await apply(OPEN);
    expect(page.textContent).toContain('Admissions 2027');
    expect(page.textContent).toContain('Class 1');
    expect(page.textContent).toContain('Birth certificate');
    expect(page.querySelector('a[href="/apply/signup"]')).not.toBeNull();
  });

  it('says plainly when admissions are not open', async () => {
    const page = await apply({ open: false, cycles: [] });
    expect(page.textContent).toContain('Admissions are not open right now.');
  });

  it('signs a new applicant up and takes them to their applications', async () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(SignupPage);
    await fixture.whenStable();
    const page = fixture.componentInstance as unknown as { form: SignupPage['form']; submit: () => void };
    page.form.setValue({ full_name: 'Asha Parent', username: 'asha.parent', email: '', phone: '', password: 'Long-pass-2027' });
    page.submit();
    const request = http.expectOne('/api/v1/applicant/signup');
    expect(request.request.body.username).toBe('asha.parent');
    request.flush({ user: makeMember('applicant') }, { status: 201, statusText: 'Created' });
    await fixture.whenStable();
    expect(navigate).toHaveBeenCalledWith('/apply/applications');
  });
});
