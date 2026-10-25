import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { HealthPage } from '../console/health-page';
import { ReportsPage } from './reports-page';

describe('Reports and health', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  it('runs a report with its provenance and asks for an export', async () => {
    const fixture = TestBed.createComponent(ReportsPage);
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/reports/').flush([{ key: 'students_by_class', title: 'Students by class or program', columns: [], can_export: true }]);
    http.expectOne('/api/v1/institution/reports/exports').flush([]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    [...root.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent?.includes('Students by class'))!.click();
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/reports/students_by_class').flush({
      key: 'students_by_class', title: 'Students by class or program', columns: ['Class or program', 'Active', 'Left'],
      rows: [['Class 6', 2, 0]], provenance: { generated_at: '2026-10-25T03:00:00Z', source: 'Eduma live records, Aster School',
      scope: 'Only records you may read', row_count: 1 },
    }); // prettier-ignore
    await fixture.whenStable();
    expect(root.querySelector('tbody')!.textContent).toContain('Class 6');
    expect(root.textContent).toContain('Only records you may read · 1 rows');
    root.querySelector<HTMLButtonElement>('#export')!.click();
    expect(http.expectOne('/api/v1/institution/reports/students_by_class/exports').request.method).toBe('POST');
  });

  it('shows unknown telemetry as unknown and acknowledges an alert', async () => {
    const fixture = TestBed.createComponent(HealthPage);
    await fixture.whenStable();
    http.expectOne('/api/v1/platform/health').flush({
      tiles: [
        { key: 'worker', label: 'Worker', status: 'unknown', value: 'never seen', threshold: 'a heartbeat every minute', source: 'run_jobs', runbook: 'x', observed_at: '2026-10-25T03:00:00Z' },
        { key: 'backup', label: 'Last backup', status: 'failing', value: '30 h ago', threshold: 'within 26 h', source: 'ops/backup.sh', runbook: 'x', observed_at: '2026-10-25T03:00:00Z' },
      ],
      alerts: [{ id: 'a1', key: 'backup', severity: 'critical', summary: 'Last backup: 30 h ago (expected within 26 h)', runbook: 'docs/operations.md#backup',
        state: 'open', opened_at: '2026-10-25T02:00:00Z', last_seen_at: '2026-10-25T03:00:00Z', owner: null }],
    }); // prettier-ignore
    http.expectOne('/api/v1/platform/backups').flush({ backups: [], drills: [] });
    http.expectOne('/api/v1/platform/jobs').flush([]);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    const badges = [...root.querySelectorAll('tbody app-status-badge span')].map((b) => [b.textContent?.trim(), b.className]);
    expect(badges).toEqual([['Unknown', 'badge badge-muted'], ['Failing', 'badge badge-danger']]);
    root.querySelector<HTMLButtonElement>('[aria-label^="Acknowledge"]')!.click();
    expect(http.expectOne('/api/v1/platform/alerts/a1/acknowledge').request.method).toBe('POST');
  });
});
