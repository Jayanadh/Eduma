import { Component, inject, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage } from '../../core/api-error';
import { load } from '../../core/load';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

type PolicyT = { guardians_can_start: boolean; calls_enabled: boolean; classes_enabled: boolean; media: boolean };

/** The institution's communication policy and its audio/video provider (S9-01, S9-08). */
@Component({
  selector: 'app-communication-settings',
  imports: [PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Administration" title="Communication" subtitle="Who may start conversations, whether calls and online classes run, and the media provider." />
      @if (policy.value(); as p) {
        <form id="policy" class="card stack section" (submit)="$event.preventDefault(); save($any($event.target))">
          <label><input id="pol-guardians" type="checkbox" [checked]="p.guardians_can_start" /> Guardians may start conversations with their child's teachers</label>
          <label><input id="pol-calls" type="checkbox" [checked]="p.calls_enabled" /> Calls between teachers and families</label>
          <label><input id="pol-classes" type="checkbox" [checked]="p.classes_enabled" /> Teacher-led online classes</label>
          <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Save</button></div>
        </form>
        <form id="media" class="card stack section" (submit)="$event.preventDefault(); media($any($event.target))">
          <h2 class="card-title">Audio and video</h2>
          <p class="small">{{ p.media ? 'The test-mode sandbox is set up: calls and classes run, with no real audio or video.' : 'Not set up: calls and classes can\\'t connect.' }} A real provider is chosen with Eduma (decision D-12). Recording is off.</p>
          <div class="field"><label for="media-secret">Sandbox secret</label><input id="media-secret" type="password" /></div>
          <div><button type="submit" class="btn btn-secondary btn-sm" [disabled]="busy()">Use the test sandbox</button></div>
        </form>
      }
    </div>
  `,
})
export class CommunicationSettings {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly policy = load(() => this.api.get<PolicyT>('communication/policy'));
  protected readonly busy = signal(false);

  private send(request: ReturnType<Api['put']>, done: string): void {
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(done);
        this.policy.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected save(form: HTMLFormElement): void {
    const on = (id: string) => form.querySelector<HTMLInputElement>(`#${id}`)!.checked;
    this.send(
      this.api.put('communication/policy', { guardians_can_start: on('pol-guardians'), calls_enabled: on('pol-calls'), classes_enabled: on('pol-classes') }),
      'Policy saved.',
    );
  }

  protected media(form: HTMLFormElement): void {
    this.send(this.api.put('communication/media', { provider: 'sandbox', secret: form.querySelector<HTMLInputElement>('#media-secret')!.value }), 'Test sandbox set up.');
  }
}
