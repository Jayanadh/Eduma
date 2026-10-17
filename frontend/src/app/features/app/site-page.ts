import { Component, inject } from '@angular/core';
import { Api } from '../../core/api/api';
import { InstitutionDetail } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { SiteEditor } from '../editor/site-editor';

/** The institution's own public page and look, edited by its admin. */
@Component({
  selector: 'app-site-page',
  imports: [LoadError, PageHeader, SiteEditor],
  template: `
    <div class="page wide">
      <app-page-header title="Public site" subtitle="Your logo, colours, fonts and the page visitors see at your web address." />
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @if (data.value(); as institution) {
        <app-site-editor class="section" [scope]="{ kind: 'institution' }" [institution]="institution" />
      }
    </div>
  `,
  styles: `
    .wide {
      max-width: none;
    }
  `,
})
export class SitePage {
  private readonly api = inject(Api);
  protected readonly data = load(() => this.api.get<InstitutionDetail>('institution'));
}
