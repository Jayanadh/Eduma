import { Component, inject, input } from '@angular/core';
import { Api } from '../../core/api/api';
import { Verification } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';

const STATUS = { current: 'Valid', superseded: 'Replaced by a newer document', revoked: 'Revoked by the institution' };

/** Public check of an issued document (S7-11): only what is needed to confirm it, nothing more. */
@Component({
  selector: 'app-verify-page',
  template: `
    <main class="verify">
      <h1 class="page-title">Document check</h1>
      @if (data.value(); as v) {
        <section class="card stack">
          <p class="status" [class.ok]="v.status === 'current'"><strong>{{ status[v.status] }}</strong>{{ v.superseded_by ? ' (' + v.superseded_by + ')' : '' }}</p>
          <dl>
            <dt>Institution</dt><dd>{{ v.institution }}</dd>
            <dt>Document</dt><dd>{{ v.kind }} {{ v.number }}</dd>
            <dt>Issued</dt><dd>{{ date(v.issued_on) }}</dd>
            <dt>Holder</dt><dd>{{ v.holder }}</dd>
          </dl>
        </section>
      } @else if (data.error()) {
        <p class="notice notice-warning">No document matches this link.</p>
      } @else {
        <p class="muted" role="status">Checking…</p>
      }
    </main>
  `,
  styles: `
    .verify {
      max-width: 560px;
      margin: 0 auto;
      padding: 24px 16px;
    }

    dl {
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 6px 16px;
      margin: 0;
    }

    dt {
      color: var(--text-muted);
    }

    .status.ok strong {
      color: var(--success, inherit);
    }
  `,
})
export class VerifyPage {
  readonly token = input.required<string>();
  private readonly api = inject(Api);
  protected readonly date = date;
  protected readonly status = STATUS;
  protected readonly data = load(
    () => this.api.get<Verification>(`public/verify/${this.token()}`),
    () => this.token(),
  );
}
