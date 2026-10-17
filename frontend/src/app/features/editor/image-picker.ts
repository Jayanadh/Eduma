import { HttpClient, HttpEventType } from '@angular/common/http';
import { Component, computed, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { apiErrorMessage } from '../../core/api-error';
import { ImageSlot, UploadedAsset } from '../../core/api/types';
import { Icon } from '../../ui/icon';

const MAX_BYTES = 5 * 1024 * 1024;

/** Choose, upload, replace or remove one image; optionally describe it for people who cannot see it. */
@Component({
  selector: 'app-image-picker',
  imports: [FormsModule, Icon],
  template: `
    <div class="picker">
      <div class="thumb">
        @if (url(); as src) {
          <img [src]="src" alt="" />
        } @else {
          <app-icon name="image" [size]="22" />
        }
      </div>
      <div class="picker-body">
        <span class="field-label">{{ label() }}</span>
        <span class="field-hint">PNG, JPEG or WebP, up to 5 MB.</span>
        <div class="row">
          <input #file type="file" hidden accept="image/png,image/jpeg,image/webp" (change)="pick($event)" />
          <button type="button" class="btn btn-secondary btn-sm" [disabled]="progress() !== null" (click)="file.click()">
            <app-icon name="upload" [size]="16" /> {{ url() ? 'Replace' : 'Upload' }}
          </button>
          @if (slot()?.asset) {
            <button type="button" class="btn btn-ghost btn-sm" (click)="remove()">Remove</button>
          }
        </div>
        @if (progress(); as percent) {
          <progress max="100" [value]="percent" [attr.aria-label]="'Uploading ' + label()"></progress>
        }
        @if (error()) {
          <span class="field-error" role="alert">{{ error() }}</span>
        }
        @if (describe() && slot(); as current) {
          <label class="sr-only" [for]="altId()">Description of {{ label() }}</label>
          <input
            class="alt"
            [id]="altId()"
            placeholder="Describe the picture (for screen readers)"
            maxlength="120"
            [ngModel]="current.alt"
            (ngModelChange)="describeAs($event)"
          />
        }
      </div>
    </div>
  `,
  styles: `
    .picker {
      display: flex;
      gap: 12px;
      align-items: flex-start;
    }

    .thumb {
      display: grid;
      flex: none;
      width: 64px;
      height: 64px;
      place-items: center;
      overflow: hidden;
      border: 1.5px solid var(--ink);
      border-radius: 12px;
      background: var(--brand-primary-soft);

      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
    }

    .picker-body {
      display: flex;
      flex: 1;
      flex-direction: column;
      gap: 6px;
      min-width: 0;
    }

    .field-label {
      font-size: 14px;
      font-weight: 700;
    }

    progress {
      width: 100%;
    }

    .alt {
      width: 100%;
      min-height: 40px;
      padding: 0 12px;
      border: 1.5px solid var(--border-strong);
      border-radius: 10px;
      font-size: 14px;
    }
  `,
})
export class ImagePicker {
  readonly slot = input<ImageSlot | null>(null);
  /** The site API's base under /api/v1/, e.g. institution/site. */
  readonly base = input.required<string>();
  readonly label = input('Image');
  readonly describe = input(true);
  readonly changed = output<ImageSlot>();
  private readonly http = inject(HttpClient);
  private static count = 0;

  protected readonly altId = signal(`alt-${++ImagePicker.count}`);
  protected readonly progress = signal<number | null>(null);
  protected readonly error = signal('');
  protected readonly url = computed(() => {
    const asset = this.slot()?.asset;
    return asset ? `/api/v1/public/assets/${asset}` : null;
  });

  protected pick(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) {
      return;
    }
    if (file.size > MAX_BYTES) {
      this.error.set('That file is over 5 MB. Choose a smaller image.');
      return;
    }
    const form = new FormData();
    form.append('file', file);
    this.error.set('');
    this.progress.set(0);
    this.http
      .post<UploadedAsset>(`/api/v1/${this.base()}/assets`, form, { reportProgress: true, observe: 'events' })
      .subscribe({
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress && event.total) {
            this.progress.set(Math.round((event.loaded / event.total) * 100));
          } else if (event.type === HttpEventType.Response && event.body) {
            this.progress.set(null);
            this.changed.emit({ asset: event.body.id, alt: this.slot()?.alt ?? '' });
          }
        },
        error: (err) => {
          this.progress.set(null);
          this.error.set(apiErrorMessage(err));
        },
      });
  }

  protected remove(): void {
    this.changed.emit({ asset: null, alt: this.slot()?.alt ?? '' });
  }

  protected describeAs(alt: string): void {
    this.changed.emit({ asset: this.slot()?.asset ?? null, alt });
  }
}
