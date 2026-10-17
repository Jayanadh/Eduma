import { inject, Service, signal } from '@angular/core';
import { CanDeactivateFn } from '@angular/router';
import { ConfirmDialog } from '../ui/confirm-dialog';

/** Whether a page holds edits that are not saved yet, so leaving it asks first. */
@Service()
export class UnsavedChanges {
  private readonly confirm = inject(ConfirmDialog);
  readonly dirty = signal(false);

  /** True when it is fine to leave: nothing unsaved, or the person agrees to lose it. */
  async confirmLeave(): Promise<boolean> {
    if (!this.dirty()) {
      return true;
    }
    const leave = await this.confirm.ask({
      title: 'Leave without saving?',
      message: 'Your changes to the page have not been saved as a draft.',
      confirmLabel: 'Leave and lose them',
      cancelLabel: 'Stay',
      tone: 'danger',
    });
    if (leave) {
      this.dirty.set(false);
    }
    return leave;
  }
}

export const leaveGuard: CanDeactivateFn<unknown> = () => inject(UnsavedChanges).confirmLeave();
