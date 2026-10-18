import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { PermissionGroup, RoleItem } from '../../core/api/types';
import { makeMe, signInAs } from '../../core/test-data';
import { RoleEditorPage } from './role-editor-page';

const REGISTRY: PermissionGroup[] = [
  {
    group: 'Organization',
    permissions: [{ name: 'organization.manage', label: 'Add and change campuses and departments', institution_only: true }],
  },
  {
    group: 'Staff',
    permissions: [
      { name: 'membership.read', label: 'See staff and their roles', institution_only: false },
      { name: 'role.manage', label: 'Create and change custom roles', institution_only: true },
    ],
  },
];

const FRONT_OFFICE: RoleItem = {
  id: 'r1',
  builtin: false,
  label: 'Front office',
  description: '',
  permissions: ['membership.read'],
  assigned_count: 3,
  is_active: true,
  version: 4,
};

describe('RoleEditorPage', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    const manager = makeMe({
      membership: {
        kind: 'staff',
        roles: [],
        permissions: ['institution.read', 'membership.read', 'role.manage'],
        restricted: false,
        status_reason: '',
      },
    });
    await signInAs(manager);
  });

  async function open() {
    const fixture = TestBed.createComponent(RoleEditorPage);
    fixture.componentRef.setInput('id', 'r1');
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/permissions').flush(REGISTRY);
    http.expectOne('/api/v1/institution/roles/r1').flush(FRONT_OFFICE);
    await fixture.whenStable();
    return fixture;
  }

  it('does not let the editor give a permission they lack', async () => {
    const fixture = await open();
    const box = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('#perm-organization\\.manage')!;
    expect(box.disabled).toBe(true);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain("You don't have this");
  });

  it('previews the change and saves it with the version it started from', async () => {
    const fixture = await open();
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLInputElement>('#perm-role\\.manage')!.click();
    root.querySelector<HTMLInputElement>('#perm-membership\\.read')!.click();
    await fixture.whenStable();
    expect(root.textContent).toContain('Adds: Create and change custom roles');
    expect(root.textContent).toContain('Removes: See staff and their roles');
    expect(root.textContent).toContain('Affects 3 people');
    root.querySelector('form')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/roles/r1');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ name: 'Front office', description: '', permissions: ['role.manage'], version: 4 });
  });
});
