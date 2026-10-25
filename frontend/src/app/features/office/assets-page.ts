import { Component, inject, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { readable } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { PageHeader } from '../../ui/page-header';
import { SearchBox } from '../../ui/search-box';
import { ToastService } from '../../ui/toast';
import { OFFICE_STYLES } from './office-styles';

export type AssetT = {
  id: string;
  tag: string;
  name: string;
  category: string;
  location: string;
  custodian: { id: string; name: string } | null;
  bookable: boolean;
  status: 'in_use' | 'maintenance' | 'disposed';
  disposal_reason: string;
};

/** The asset register (S10B-08): who holds what and where, maintenance, and disposal with its reason. */
@Component({
  selector: 'app-assets-page',
  imports: [PageHeader, SearchBox],
  template: `
    <div class="page">
      <app-page-header eyebrow="Campus" title="Assets" subtitle="Every change of hands, repair and disposal is kept." />
      <section class="card stack section">
        <app-search-box id="asset-search" label="Search assets" (search)="query.set($event)" />
        <ul class="rows">
          @for (a of assets.value() ?? []; track a.id) {
            <li>
              <span><strong>{{ a.tag }}</strong> {{ a.name }} <span class="muted small">· {{ readable(a.status) }}{{ a.category ? ' · ' + a.category : '' }}{{ a.location ? ' · ' + a.location : '' }}{{ a.custodian ? ' · with ' + a.custodian.name : '' }}{{ a.bookable ? ' · bookable' : '' }}{{ a.disposal_reason ? ' · ' + a.disposal_reason : '' }}</span></span>
              @if (a.status !== 'disposed') {
                <span class="actions">
                  <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Hand over ' + a.tag" (click)="transfer(a)">Hand over</button>
                  @if (a.status === 'in_use') {
                    <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="'Send ' + a.tag + ' for maintenance'" (click)="maintenance(a)">Maintenance</button>
                  } @else {
                    <button type="button" class="btn btn-secondary btn-sm" [attr.aria-label]="a.tag + ' back in use'" (click)="act(a, 'back', {}, 'Back in use.')">Back in use</button>
                  }
                  <button type="button" class="btn btn-danger btn-sm" [attr.aria-label]="'Dispose of ' + a.tag" (click)="dispose(a)">Dispose</button>
                </span>
              }
            </li>
          } @empty {
            <li class="muted small">No assets yet.</li>
          }
        </ul>
        <form id="add-asset" class="row" (submit)="$event.preventDefault(); add($any($event.target))">
          <div class="field"><label for="asset-tag">Tag</label><input id="asset-tag" maxlength="30" required /></div>
          <div class="field grow"><label for="asset-name">Name</label><input id="asset-name" maxlength="120" required /></div>
          <div class="field"><label for="asset-category">Category</label><input id="asset-category" maxlength="60" /></div>
          <div class="field"><label for="asset-location">Location</label><input id="asset-location" maxlength="80" /></div>
          <label><input id="asset-bookable" type="checkbox" /> Can be booked</label>
          <button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Add asset</button>
        </form>
      </section>
    </div>
  `,
  styles: [OFFICE_STYLES],
})
export class AssetsPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  private readonly dialog = inject(ConfirmDialog);
  protected readonly readable = readable;
  protected readonly query = signal('');
  protected readonly assets = load(
    () => this.api.get<AssetT[]>('institution/stores/assets', this.query() ? { search: this.query() } : {}),
    () => this.query(),
  );
  protected readonly busy = signal(false);

  private run(request: Observable<unknown>, done: string, after?: () => void): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        after?.();
        this.assets.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected act(a: AssetT, action: string, body: object, done: string): void {
    this.run(this.api.post(`institution/stores/assets/${a.id}/${action}`, body), done);
  }

  protected async transfer(a: AssetT): Promise<void> {
    const username = await this.dialog.prompt({ title: `Hand over ${a.tag}`, label: 'Username of the new holder', confirmLabel: 'Hand over', required: true });
    if (username) {
      this.act(a, 'transfer', { username }, 'Handed over.');
    }
  }

  protected async maintenance(a: AssetT): Promise<void> {
    const note = await this.dialog.prompt({ title: `Maintenance for ${a.tag}`, label: "What's wrong", confirmLabel: 'Send for maintenance', required: true });
    if (note) {
      this.act(a, 'maintenance', { note }, 'Sent for maintenance; it cannot be booked meanwhile.');
    }
  }

  protected async dispose(a: AssetT): Promise<void> {
    const reason = await this.dialog.prompt({
      title: `Dispose of ${a.tag}`,
      label: 'Reason and who authorised it',
      confirmLabel: 'Dispose',
      tone: 'danger',
      required: true,
    });
    if (reason) {
      this.act(a, 'dispose', { reason }, 'Disposed.');
    }
  }

  protected add(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!;
    const body = {
      tag: field('asset-tag').value.trim(),
      name: field('asset-name').value.trim(),
      category: field('asset-category').value.trim(),
      location: field('asset-location').value.trim(),
      bookable: field('asset-bookable').checked,
    };
    this.run(this.api.post('institution/stores/assets', body), 'Asset added.', () => form.reset());
  }
}
