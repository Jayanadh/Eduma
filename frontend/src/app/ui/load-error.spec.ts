import { TestBed } from '@angular/core/testing';
import { LoadError } from './load-error';

async function render(message: string | null) {
  const fixture = TestBed.createComponent(LoadError);
  fixture.componentRef.setInput('message', message);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('LoadError', () => {
  it('shows nothing until something has failed', async () => {
    expect((await render('')).querySelector('button')).toBeNull();
    expect((await render(null)).querySelector('button')).toBeNull();
  });

  it('says what failed and offers to try again', async () => {
    const element = await render('Cannot reach the server.');
    expect(element.querySelector('[role="alert"]')?.textContent).toContain('Cannot reach the server.');
    expect(element.querySelector('button')?.textContent).toContain('Try again');
  });
});
