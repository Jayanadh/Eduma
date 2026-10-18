import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SettingDetail, SettingRevisionItem } from '../../core/api/types';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { SettingEditorPage } from './setting-editor-page';

function revision(overrides: Partial<SettingRevisionItem> = {}): SettingRevisionItem {
  return {
    id: 'r2',
    number: 2,
    status: 'draft',
    version: 3,
    value: 6,
    description: 'Starts in June',
    effective_from: null,
    reason: '',
    return_note: '',
    created_by_name: 'Aster School Admin',
    submitted_by_name: null,
    submitted_at: null,
    approved_by_name: null,
    published_at: null,
    mine: false,
    can_approve: false,
    ...overrides,
  };
}

function setting(overrides: Partial<SettingDetail> = {}): SettingDetail {
  return {
    key: 'academic.year_start',
    label: 'Academic year starts',
    help: 'The month your academic year begins.',
    kind: 'month',
    needs_approval: false,
    value_now: 6,
    description_now: 'Starts in June',
    scheduled: null,
    open: { id: 'r2', status: 'draft', version: 3 },
    draft: revision(),
    pending: null,
    preview: [],
    choices: [],
    history: { count: 0, results: [] },
    ...overrides,
  };
}

describe('SettingEditorPage', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ConfirmDialog, useValue: { prompt: () => Promise.resolve('Not this term') } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  async function open(detail: SettingDetail) {
    const fixture = TestBed.createComponent(SettingEditorPage);
    fixture.componentRef.setInput('key', detail.key);
    await fixture.whenStable();
    http.expectOne((request) => request.url === `/api/v1/institution/settings/${detail.key}`).flush(detail);
    await fixture.whenStable();
    return fixture;
  }

  function button(root: HTMLElement, text: string): HTMLButtonElement | undefined {
    return [...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  }

  it('saves the draft and shows what the change would do', async () => {
    const fixture = await open(setting());
    const root = fixture.nativeElement as HTMLElement;
    const month = root.querySelector<HTMLSelectElement>('#setting-month')!;
    month.value = '4';
    month.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    button(root, 'Save draft')!.click();
    const request = http.expectOne('/api/v1/institution/settings/academic.year_start/draft');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ version: 3, value: 4 });
    const preview = ['The 2026–27 year runs 1 Apr 2026 – 31 Mar 2027.'];
    request.flush(setting({ draft: revision({ value: 4, version: 4 }), preview }));
    await fixture.whenStable();
    expect(root.textContent).toContain('The 2026–27 year runs 1 Apr 2026 – 31 Mar 2027.');
  });

  it('publishes or sends for approval, as the setting requires', async () => {
    let fixture = await open(setting());
    expect(button(fixture.nativeElement, 'Publish')).toBeDefined();
    fixture.destroy();
    fixture = await open(setting({ key: 'access.role_approval', kind: 'bool', needs_approval: true, value_now: false }));
    expect(button(fixture.nativeElement, 'Send for approval')).toBeDefined();
  });

  it('sends the start day and reason with the change', async () => {
    const fixture = await open(setting());
    const root = fixture.nativeElement as HTMLElement;
    const starts = root.querySelector<HTMLInputElement>('#setting-starts')!;
    starts.value = '2027-04-01';
    starts.dispatchEvent(new Event('input'));
    const why = root.querySelector<HTMLTextAreaElement>('#setting-why')!;
    why.value = 'Board calendar';
    why.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    button(root, 'Publish')!.click();
    const request = http.expectOne('/api/v1/institution/settings/academic.year_start/draft/submit');
    expect(request.request.body).toEqual({ version: 3, effective_from: '2027-04-01', reason: 'Board calendar' });
  });

  it('lets another publisher approve or return a waiting change', async () => {
    const pending = revision({
      status: 'pending',
      submitted_by_name: 'Aster School Admin',
      can_approve: true,
      effective_from: '2026-11-01',
    });
    const fixture = await open(setting({ draft: null, pending, open: { id: 'r2', status: 'pending', version: 3 } }));
    const root = fixture.nativeElement as HTMLElement;
    expect(button(root, 'Approve')).toBeDefined();
    button(root, 'Return with a note')!.click();
    await fixture.whenStable();
    const request = http.expectOne('/api/v1/institution/settings/academic.year_start/revisions/r2/return');
    expect(request.request.body).toEqual({ version: 3, note: 'Not this term' });
  });
});
