import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Campus, Department } from '../../core/api/types';
import { CampusForm } from './campus-form';
import { DepartmentForm } from './department-form';

const MAIN: Campus = { id: 'c1', code: 'MAIN', name: 'Main campus', address: '', is_active: true, version: 1 };
const SCI: Department = {
  id: 'd1',
  code: 'SCI',
  name: 'Science',
  campus: { id: 'c1', name: 'Main campus' },
  parent: null,
  is_active: true,
  version: 1,
};

function type(root: HTMLElement, selector: string, value: string): void {
  const field = root.querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
  field.value = value;
  field.dispatchEvent(new Event(field.tagName === 'SELECT' ? 'change' : 'input'));
}

describe('Organization forms', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  it('adds a campus and says so', async () => {
    const fixture = TestBed.createComponent(CampusForm);
    fixture.componentRef.setInput('campus', null);
    let saved = 0;
    fixture.componentInstance.saved.subscribe(() => saved++);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    type(root, '#campus-code', 'city');
    type(root, '#campus-name', 'City campus');
    root.querySelector('form')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/campuses');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ code: 'city', name: 'City campus', address: '' });
    request.flush({ ...MAIN, id: 'c2', code: 'CITY', name: 'City campus' }, { status: 201, statusText: 'Created' });
    expect(saved).toBe(1);
  });

  it('shows a refused code under the Code field', async () => {
    const fixture = TestBed.createComponent(CampusForm);
    fixture.componentRef.setInput('campus', MAIN);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    type(root, '#campus-code', 'X');
    root.querySelector('form')!.dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/institution/campuses/c1');
    expect(request.request.body.version).toBe(1);
    request.flush(
      {
        code: 'validation_failed',
        detail: 'Use 2–20 letters, digits or dashes.',
        errors: [{ field: 'code', message: 'Use 2–20 letters, digits or dashes.' }],
      },
      { status: 422, statusText: 'Unprocessable' },
    );
    await fixture.whenStable();
    expect(root.querySelector('.field-error')?.textContent).toContain('Use 2–20 letters');
  });

  it('hides the campus choice when a department sits under another', async () => {
    const fixture = TestBed.createComponent(DepartmentForm);
    fixture.componentRef.setInput('department', null);
    fixture.componentRef.setInput('campuses', [MAIN]);
    fixture.componentRef.setInput('departments', [SCI]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('#department-campus')).not.toBeNull();
    type(root, '#department-parent', 'd1');
    await fixture.whenStable();
    expect(root.querySelector('#department-campus')).toBeNull();
  });

  it('never offers a department, or one below it, as its own parent', async () => {
    const phy: Department = { ...SCI, id: 'd2', code: 'PHY', name: 'Physics', parent: { id: 'd1', name: 'Science' } };
    const fixture = TestBed.createComponent(DepartmentForm);
    fixture.componentRef.setInput('department', SCI);
    fixture.componentRef.setInput('campuses', [MAIN]);
    fixture.componentRef.setInput('departments', [SCI, phy]);
    await fixture.whenStable();
    const options = [...(fixture.nativeElement as HTMLElement).querySelectorAll('#department-parent option')];
    expect(options.map((option) => option.textContent?.trim())).toEqual(['None']);
  });
});
