import { effect, signal, untracked, WritableSignal } from '@angular/core';
import { Observable } from 'rxjs';
import { apiErrorMessage } from './api-error';

/** Something a page loads from the API: its value, whether it is loading, and why it failed. */
export type Loaded<T> = {
  readonly value: WritableSignal<T | null>;
  readonly loading: WritableSignal<boolean>;
  readonly error: WritableSignal<string>;
  reload(): void;
};

/**
 * Loads `source` once the component's inputs are set, again whenever the signals read by `key` change (such as the
 * id in the address), and on every reload(). Keeps the last value while reloading, so the page does not flicker.
 * Call it in a field initializer (it needs the injection context).
 */
export function load<T>(source: () => Observable<T>, key?: () => unknown): Loaded<T> {
  const value = signal<T | null>(null);
  const loading = signal(true);
  const error = signal('');
  let run = 0;
  const reload = () => {
    const mine = ++run;
    loading.set(true);
    error.set('');
    source().subscribe({
      next: (result) => {
        if (mine === run) {
          value.set(result);
          loading.set(false);
        }
      },
      error: (err) => {
        if (mine === run) {
          error.set(apiErrorMessage(err));
          loading.set(false);
        }
      },
    });
  };
  effect(() => {
    key?.();
    untracked(reload);
  });
  return { value, loading, error, reload };
}
