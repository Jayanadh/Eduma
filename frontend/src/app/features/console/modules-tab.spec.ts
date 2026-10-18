import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { InstitutionDetail } from '../../core/api/types';
import { MODULE_CATALOGUE } from '../../core/test-data';
import { ModulesTab } from './modules-tab';

type Tab = { chosen: { set: (keys: string[]) => void }; save: () => void };

describe('ModulesTab', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  async function open() {
    const fixture = TestBed.createComponent(ModulesTab);
    fixture.componentRef.setInput('institution', { id: 'i1', version: 7, modules: ['students'] } as InstitutionDetail);
    await fixture.whenStable();
    http.expectOne('/api/v1/platform/modules').flush(MODULE_CATALOGUE);
    await fixture.whenStable();
    return { fixture, tab: fixture.componentInstance as unknown as Tab };
  }

  it('shows the plan and saves a change with the version it started from', async () => {
    const { fixture, tab } = await open();
    const ticked = [...(fixture.nativeElement as HTMLElement).querySelectorAll<HTMLInputElement>('input:checked')];
    expect(ticked.length).toBe(1);
    tab.chosen.set(['fees', 'students']);
    tab.save();
    const request = http.expectOne('/api/v1/platform/institutions/i1');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ version: 7, modules: ['fees', 'students'] });
  });

  it('shows the server reason when a list is refused', async () => {
    const { fixture, tab } = await open();
    tab.save();
    http.expectOne('/api/v1/platform/institutions/i1').flush(
      {
        code: 'validation_failed',
        detail: 'Fees needs Students and guardians.',
        errors: [{ field: 'modules', message: 'Fees needs Students and guardians.' }],
      },
      { status: 422, statusText: 'Unprocessable' },
    );
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Fees needs Students and guardians.');
  });
});
