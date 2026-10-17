import { TestBed } from '@angular/core/testing';
import { ConfirmDialog, ConfirmHost } from './confirm-dialog';

describe('ConfirmDialog', () => {
  let dialog: ConfirmDialog;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [ConfirmHost] });
    dialog = TestBed.inject(ConfirmDialog);
  });

  async function host() {
    const fixture = TestBed.createComponent(ConfirmHost);
    await fixture.whenStable();
    return fixture;
  }

  it('resolves true on confirm and false on cancel', async () => {
    const fixture = await host();
    const yes = dialog.ask({ title: 'Sure?', confirmLabel: 'Yes' });
    await fixture.whenStable();
    (fixture.nativeElement.querySelector('button[type=submit]') as HTMLButtonElement).click();
    expect(await yes).toBe(true);

    const no = dialog.ask({ title: 'Sure?', confirmLabel: 'Yes' });
    await fixture.whenStable();
    (fixture.nativeElement.querySelector('button[type=button]') as HTMLButtonElement).click();
    expect(await no).toBe(false);
  });

  it('a newer question cancels the open one', async () => {
    const first = dialog.ask({ title: 'One', confirmLabel: 'OK' });
    void dialog.ask({ title: 'Two', confirmLabel: 'OK' });
    expect(await first).toBe(false);
  });

  it('a prompt needs an answer before it confirms, then resolves with it', async () => {
    const fixture = await host();
    const answer = dialog.prompt({ title: 'Why?', label: 'Reason', confirmLabel: 'Save' });
    await fixture.whenStable();
    const form = fixture.nativeElement.querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain('Fill this in to continue.');

    const input = fixture.nativeElement.querySelector('#confirm-answer') as HTMLInputElement;
    input.value = '  Holiday  ';
    input.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    form.dispatchEvent(new Event('submit'));
    expect(await answer).toBe('Holiday');
  });

  it('a cancelled prompt resolves null', async () => {
    const answer = dialog.prompt({ title: 'Why?', label: 'Reason', confirmLabel: 'Save' });
    dialog.open()?.answer(false);
    expect(await answer).toBeNull();
  });
});
