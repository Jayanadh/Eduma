import { Component } from '@angular/core';
import { PageHeader } from '../../ui/page-header';
import { AuditList } from './audit-list';

@Component({
  selector: 'app-audit-page',
  imports: [AuditList, PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Eduma platform" title="Audit log" subtitle="Who did what, and when. Nothing here can be changed or deleted." />
      <app-audit-list class="section" path="platform/audit" filters />
    </div>
  `,
})
export class AuditPage {}
