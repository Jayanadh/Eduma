import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { OfferingsSection, Revision, SiteContent } from '../../core/api/types';
import { EDUMA_THEME } from '../../core/test-data';
import { SiteEditor } from './site-editor';

type Editor = {
  content: SiteContent;
  changed(): void;
  save(): void;
  moveSection(index: number, delta: -1 | 1): void;
  toggleSection(index: number): void;
  canAdd(section: SiteContent['sections'][number]): boolean;
  setTheme(name: 'primary_color', value: string): void;
  conflict(): boolean;
  dirty(): boolean;
  previewStyle(): Record<string, string>;
};

const offerings: OfferingsSection = {
  id: 'offerings',
  type: 'offerings',
  visible: true,
  eyebrow: 'What we offer',
  title: 'Programmes',
  subtitle: '',
  items: Array.from({ length: 6 }, (_, i) => ({ title: `P${i}`, text: '', image: null, tags: [], cta: null })),
};

function draft(): Revision {
  return {
    id: 'r1',
    number: 1,
    status: 'draft',
    version: 3,
    theme: EDUMA_THEME,
    logo: null,
    created_at: '2026-10-17T00:00:00Z',
    published_at: null,
    published_by_name: null,
    content: {
      sections: [
        {
          id: 'hero',
          type: 'hero',
          visible: true,
          eyebrow: '',
          title: 'Welcome to Aster School',
          subtitle: '',
          primary_cta: { label: 'Visit', href: '#s-faq' },
          secondary_cta: null,
          images: [],
          badge: null,
          stickers: [],
        },
        offerings,
      ],
    },
  };
}

describe('SiteEditor', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  async function open(): Promise<Editor> {
    const fixture = TestBed.createComponent(SiteEditor);
    fixture.componentRef.setInput('scope', { kind: 'institution' });
    fixture.componentRef.setInput('institution', {
      slug: 'aster',
      display_name: 'Aster School',
      category: 'school',
      contact_email: '',
      contact_phone: '',
      address: '',
      lifecycle_status: 'active',
    });
    await fixture.whenStable();
    http.expectOne('/api/v1/institution/site/draft').flush(draft());
    await fixture.whenStable();
    return fixture.componentInstance as unknown as Editor;
  }

  it('keeps local edits on a 409 and offers reload', async () => {
    const editor = await open();
    editor.content.sections[0].title = 'My new title';
    editor.changed();
    expect(editor.dirty()).toBe(true);
    editor.save();
    const request = http.expectOne('/api/v1/institution/site/draft');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body.version).toBe(3);
    request.flush({ code: 'version_conflict', current_version: 4 }, { status: 409, statusText: 'Conflict' });
    expect(editor.conflict()).toBe(true);
    expect(editor.content.sections[0].title).toBe('My new title');
    expect(editor.dirty()).toBe(true);
  });

  it('never moves a section above the hero', async () => {
    const editor = await open();
    editor.moveSection(1, -1);
    expect(editor.content.sections.map((section) => section.type)).toEqual(['hero', 'offerings']);
    editor.moveSection(0, 1);
    expect(editor.content.sections.map((section) => section.type)).toEqual(['hero', 'offerings']);
  });

  it('cannot hide the hero', async () => {
    const editor = await open();
    editor.toggleSection(0);
    expect(editor.content.sections[0].visible).toBe(true);
    editor.toggleSection(1);
    expect(editor.content.sections[1].visible).toBe(false);
  });

  it('disables Add at the item limit', async () => {
    const editor = await open();
    expect(editor.canAdd(editor.content.sections[1])).toBe(false);
    (editor.content.sections[1] as OfferingsSection).items.pop();
    expect(editor.canAdd(editor.content.sections[1])).toBe(true);
  });

  it('preview applies the draft theme locally', async () => {
    const editor = await open();
    editor.setTheme('primary_color', '#FFD43B');
    expect(editor.previewStyle()['--brand-primary']).toBe('#FFD43B');
    expect(editor.previewStyle()['--brand-on-primary']).toBe('#17132B');
    expect(document.documentElement.style.getPropertyValue('--brand-primary')).not.toBe('#FFD43B');
  });
});
