import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { StaffDetail } from '../../core/api/types';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { ToastService } from '../../ui/toast';
import { AddStaffPage } from './add-staff-page';
import { ScopePicker } from './scope-picker';
import { StaffDetailPage } from './staff-detail-page';

const EMPTY_PAGE = { count: 0, next: null, previous: null, results: [] };

function detail(overrides: Partial<StaffDetail> = {}): StaffDetail {
  return {
    id: 'm1',
    full_name: 'Ravi Kumar',
    username: 'ravi.kumar',
    status: 'active',
    roles: [{ label: 'Teacher / Faculty', scope_label: 'Science' }],
    email: '',
    mobile: '',
    last_login: null,
    must_change_password: true,
    version: 2,
    assignments: [
      {
        id: 'a1',
        role_label: 'Teacher / Faculty',
        scope_type: 'department',
        scope_label: 'Science',
        starts_on: '2026-10-18',
        ends_on: null,
        status: 'active',
        end_reason: '',
        in_effect: true,
      },
    ],
    can_manage: true,
    ...overrides,
  };
}

describe('Staff pages', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ConfirmDialog, useValue: { prompt: () => Promise.resolve('Moved') } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  it('suggests a login ID from the name until it is typed by hand', async () => {
    const fixture = TestBed.createComponent(AddStaffPage);
    await fixture.whenStable();
    const page = fixture.componentInstance as unknown as { form: AddStaffPage['form'] };
    page.form.controls.full_name.setValue('Ravi Kumar');
    expect(page.form.controls.username.value).toBe('ravi.kumar');
    page.form.controls.username.setValue('rk');
    page.form.controls.username.markAsDirty();
    page.form.controls.full_name.setValue('Ravi K');
    expect(page.form.controls.username.value).toBe('rk');
  });

  it('asks for a campus only when the role is for a campus', async () => {
    const fixture = TestBed.createComponent(ScopePicker);
    fixture.componentRef.setInput('campuses', [{ id: 'c1', name: 'City campus' }]);
    fixture.componentRef.setInput('departments', [{ id: 'd1', name: 'Science' }]);
    fixture.componentRef.setInput('value', { scope_type: 'institution', campus: null, department: null });
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('#scope-campus')).toBeNull();
    fixture.componentRef.setInput('value', { scope_type: 'campus', campus: null, department: null });
    await fixture.whenStable();
    expect(root.querySelector('#scope-campus')).not.toBeNull();
    expect(root.querySelector('#scope-department')).toBeNull();
  });

  async function openDetail(person: StaffDetail) {
    const fixture = TestBed.createComponent(StaffDetailPage);
    fixture.componentRef.setInput('id', 'm1');
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/staff/m1').flush(person);
    for (const request of http.match(() => true)) {
      request.flush(EMPTY_PAGE);
    }
    await fixture.whenStable();
    return fixture;
  }

  it('offers changes only to people the viewer may manage', async () => {
    const fixture = await openDetail(detail({ can_manage: false }));
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Teacher / Faculty');
    expect(text).not.toContain('Reset password');
    expect(text).not.toContain('End');
  });

  it('shows why the last Institution Admin cannot lose the role', async () => {
    const fixture = await openDetail(detail());
    const end = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'End',
    )!;
    end.click();
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/staff/m1/assignments/a1/end').flush(
      { code: 'last_admin', detail: 'Add another Institution Admin first.', errors: [] },
      { status: 409, statusText: 'Conflict' },
    );
    await fixture.whenStable();
    const messages = TestBed.inject(ToastService).messages().map((toast) => toast.text);
    expect(messages).toContain('Add another Institution Admin first.');
  });
});
