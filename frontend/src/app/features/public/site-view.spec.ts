import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { PublicSite, Section } from '../../core/api/types';
import { SiteStore } from '../../core/site-store';
import { makeSite, onSite } from '../../core/test-data';
import { LandingPage } from './landing-page';
import { SiteView } from './site-view';

const faq: Section = {
  id: 'faq',
  type: 'faq',
  visible: false,
  eyebrow: 'FAQ',
  title: 'Questions',
  subtitle: '',
  cta: null,
  items: [{ q: 'When?', a: 'Soon.' }],
};
const steps: Section = {
  id: 'steps',
  type: 'steps',
  visible: true,
  eyebrow: 'How',
  title: 'How admission works',
  items: [{ title: 'Apply', text: 'Fill the form.', icon: 'apply' }],
};

function withSections(site: PublicSite, extra: Section[]): PublicSite {
  if (!('content' in site)) {
    return site;
  }
  return { ...site, content: { sections: [...site.content.sections, ...extra] } } as PublicSite;
}

async function render(site: PublicSite, preview = false) {
  const fixture = TestBed.createComponent(SiteView);
  fixture.componentRef.setInput('site', site);
  fixture.componentRef.setInput('preview', preview);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('SiteView', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  it('renders only visible sections in order', async () => {
    const page = await render(withSections(makeSite('institution'), [faq, steps]));
    const ids = Array.from(page.querySelectorAll('main > section')).map((section) => section.id);
    expect(ids).toEqual(['s-hero', 's-steps']);
    expect(page.querySelector('h1')?.textContent).toContain('Welcome to Aster School');
  });

  it('shows Sign in for an institution but not for the platform or in a preview', async () => {
    const institution = await render(makeSite('institution'));
    expect(institution.querySelector('a[href="/login"]')?.textContent).toContain('Sign in');
    expect(institution.querySelector('a[href="/apply"]')?.textContent).toContain('Apply');
    const platform = await render(makeSite('platform'));
    expect(platform.querySelector('a[href="/login"]')).toBeNull();
    const preview = await render(makeSite('institution'), true);
    expect(preview.querySelector('a[href="/login"]')).toBeNull();
  });

  it('falls back to a tinted tile when an image has no url', async () => {
    const site = makeSite('institution');
    if ('content' in site && site.content.sections[0].type === 'hero') {
      site.content.sections[0].images = [{ asset: null, alt: 'Our campus', url: null }];
    }
    const page = await render(site);
    expect(page.querySelector('.slot-empty')).not.toBeNull();
    expect(page.querySelector('.hero img')).toBeNull();
  });

  it('shows an uploaded image with its description', async () => {
    const site = makeSite('institution');
    if ('content' in site && site.content.sections[0].type === 'hero') {
      site.content.sections[0].images = [{ asset: 'a1', alt: 'Our campus', url: '/api/v1/public/assets/a1' }];
    }
    const image = (await render(site)).querySelector('.hero img') as HTMLImageElement;
    expect(image.getAttribute('src')).toBe('/api/v1/public/assets/a1');
    expect(image.alt).toBe('Our campus');
  });

  it('lists the contact details in the footer', async () => {
    const footer = (await render(makeSite('institution'))).querySelector('footer') as HTMLElement;
    expect(footer.querySelector('a[href="tel:+91 90000 00001"]')).not.toBeNull();
    expect(footer.textContent).toContain('Powered by Eduma');
  });
});

describe('LandingPage', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  afterEach(() => TestBed.inject(HttpTestingController).verify());

  async function land(site: PublicSite) {
    await onSite(site);
    const fixture = TestBed.createComponent(LandingPage);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('opening soon shows the hero title and no other sections', async () => {
    const page = await land(withSections(makeSite('institution', { mode: 'opening_soon' }), [steps]));
    expect(page.querySelector('h1')?.textContent).toContain('Welcome to Aster School');
    expect(page.textContent).toContain('Opening soon');
    expect(page.querySelector('#s-steps')).toBeNull();
    expect(page.querySelector('a[href="/login"]')).not.toBeNull();
  });

  it('offers to try again when the site could not be reached, instead of saying it does not exist', async () => {
    const loaded = TestBed.inject(SiteStore).load();
    TestBed.inject(HttpTestingController)
      .expectOne('/api/v1/public/site')
      .flush(null, { status: 503, statusText: 'Unavailable' });
    await loaded;
    const fixture = TestBed.createComponent(LandingPage);
    await fixture.whenStable();
    const page = fixture.nativeElement as HTMLElement;
    expect(page.textContent).not.toContain('There is no Eduma site at this address');
    expect(page.querySelector('[role="alert"]')?.textContent).toContain('could not be reached');
    expect(page.querySelector('button')?.textContent).toContain('Try again');
  });

  it('says an unavailable institution is unavailable, with no sign-in', async () => {
    const page = await land({ kind: 'institution', mode: 'unavailable', institution: { display_name: 'Aster School' } });
    expect(page.querySelector('h1')?.textContent).toContain('Aster School is temporarily unavailable.');
    expect(page.querySelector('a[href="/login"]')).toBeNull();
  });

  it('renders the full page for an active institution', async () => {
    const page = await land(withSections(makeSite('institution'), [steps]));
    expect(page.querySelector('#s-steps')).not.toBeNull();
  });
});
