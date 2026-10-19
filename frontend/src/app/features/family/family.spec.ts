import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { FamilyChild } from '../../core/api/types';
import { FamilyChildPage } from './family-child-page';
import { FamilyHome } from './family-home';

const ENROLLMENT = {
  academic_year: '2027–28',
  place_code: 'C6',
  place_label: 'Class 6',
  campus_name: 'Main campus',
  entry_date: '2027-06-01',
  status: 'active',
  exit_date: null,
  exit_reason: '',
};

const SHARED: FamilyChild = {
  id: 's1',
  full_name: 'Arjun Demo',
  shared: true,
  number: '2027-0001',
  status: 'active',
  left_on: null,
  enrollment: ENROLLMENT,
};

describe('Family portal', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  it('lists shared children with their class and unshared ones without', async () => {
    const fixture = TestBed.createComponent(FamilyHome);
    await fixture.whenStable();
    http.expectOne('/api/v1/family/children').flush([SHARED, { id: 's2', full_name: 'Diya Demo', shared: false }]);
    await fixture.whenStable();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('2027-0001');
    expect(text).toContain('Class 6');
    expect(text).toContain('Diya Demo');
    expect(text).toContain('Your school has not shared this record with you.');
    expect(text.match(/2027-000/g)?.length).toBe(1);
  });

  it('says when nothing is shared yet', async () => {
    const fixture = TestBed.createComponent(FamilyHome);
    await fixture.whenStable();
    http.expectOne('/api/v1/family/children').flush([]);
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Nothing is shared here yet');
  });

  it('shows when a child has left', async () => {
    const fixture = TestBed.createComponent(FamilyChildPage);
    fixture.componentRef.setInput('id', 's1');
    await fixture.whenStable();
    http
      .expectOne('/api/v1/family/children/s1')
      .flush({ ...SHARED, status: 'withdrawn', left_on: '2027-03-01', enrollment: { ...ENROLLMENT, status: 'ended' } });
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Left on 01 Mar 2027');
  });
});
