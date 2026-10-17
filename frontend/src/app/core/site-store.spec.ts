import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Theme } from './api/types';
import { SiteStore, themeVariables } from './site-store';
import { EDUMA_THEME, makeSite, onSite } from './test-data';

describe('SiteStore', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
  });

  afterEach(() => {
    TestBed.inject(HttpTestingController).verify();
    document.documentElement.removeAttribute('style');
  });

  it('maps a theme to CSS variables', () => {
    const vars = themeVariables({
      ...EDUMA_THEME,
      primary_color: '#5B3FD9',
      secondary_text: '#8A6500',
      heading_font: 'fredoka',
      body_font: 'nunito',
    } as Theme);
    expect(vars['--brand-primary']).toBe('#5B3FD9');
    expect(vars['--brand-on-primary']).toBe('#FFFFFF');
    expect(vars['--brand-secondary-text']).toBe('#8A6500');
    expect(vars['--font-heading']).toContain('Fredoka');
    expect(vars['--font-body']).toContain('Nunito');
    expect(Object.keys(vars)).toHaveLength(8);
  });

  it('falls back to the default fonts for an unknown code', () => {
    const vars = themeVariables({ ...EDUMA_THEME, heading_font: 'comic-sans' });
    expect(vars['--font-heading']).toContain('Bricolage');
  });

  it('treats 404 as an unknown site', async () => {
    await onSite(null);
    const store = TestBed.inject(SiteStore);
    expect(store.kind()).toBe('unknown');
    expect(store.site()).toBeNull();
  });

  it('applies an institution theme, title and favicon', async () => {
    await onSite(makeSite('institution', { logo_url: '/api/v1/public/assets/abc' }));
    const store = TestBed.inject(SiteStore);
    expect(store.kind()).toBe('institution');
    expect(store.institutionName()).toBe('Aster School');
    expect(document.documentElement.style.getPropertyValue('--brand-primary')).toBe('#5B3FD9');
    expect(document.title).toBe('Aster School');
    expect(document.querySelector<HTMLLinkElement>('link[rel="icon"]')?.href).toContain(
      '/api/v1/public/assets/abc',
    );
  });

  it('names an unavailable institution', async () => {
    await onSite({ kind: 'institution', mode: 'unavailable', institution: { display_name: 'Aster School' } });
    expect(TestBed.inject(SiteStore).institutionName()).toBe('Aster School');
  });
});
