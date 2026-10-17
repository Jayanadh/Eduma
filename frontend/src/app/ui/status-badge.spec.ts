import { TestBed } from '@angular/core/testing';
import { StatusBadge } from './status-badge';

async function render(status: string, label?: string) {
  const fixture = TestBed.createComponent(StatusBadge);
  fixture.componentRef.setInput('status', status);
  if (label !== undefined) {
    fixture.componentRef.setInput('label', label);
  }
  await fixture.whenStable();
  return (fixture.nativeElement as HTMLElement).querySelector('.badge') as HTMLElement;
}

describe('StatusBadge', () => {
  beforeEach(() => TestBed.configureTestingModule({ imports: [StatusBadge] }));

  it('colours lifecycle states by what they mean', async () => {
    expect((await render('active')).classList).toContain('badge-success');
    expect((await render('setup')).classList).toContain('badge-info');
    expect((await render('suspended')).classList).toContain('badge-warning');
    expect((await render('archived')).classList).toContain('badge-muted');
    expect((await render('published')).classList).toContain('badge-success');
    expect((await render('something_new')).classList).toContain('badge-muted');
  });

  it('uses plain words', async () => {
    expect((await render('setup')).textContent?.trim()).toBe('Setting up');
    expect((await render('engineering_college')).textContent?.trim()).toBe('Engineering college');
  });

  it('prefers an explicit label', async () => {
    expect((await render('active', 'Live')).textContent?.trim()).toBe('Live');
  });
});
