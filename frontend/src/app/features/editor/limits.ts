import { ImageSlot, Section, SectionType } from '../../core/api/types';

/** The same limits the server checks (backend sites/content.py), so the editor never offers more than it accepts. */
export const ITEM_LIMITS: Partial<Record<SectionType, number>> = {
  offerings: 6,
  steps: 6,
  people: 6,
  testimonials: 6,
  faq: 12,
};
export const IMAGE_LIMITS: Partial<Record<SectionType, number>> = { hero: 3, gallery: 8 };

export const SECTION_LABELS: Readonly<Record<SectionType, string>> = {
  hero: 'Top of the page',
  offerings: 'What you offer',
  steps: 'Steps',
  people: 'People',
  gallery: 'Photo gallery',
  testimonials: 'Testimonials',
  feature: 'Highlight band',
  faq: 'Questions and answers',
};

export const STEP_ICON_CHOICES = ['apply', 'calendar', 'chat', 'book', 'check', 'star', 'users', 'home', 'award', 'map'];

/** The list a section's "Add" button grows: its items, or its images for the hero and the gallery. */
export function listOf(section: Section): unknown[] {
  if (section.type === 'hero' || section.type === 'gallery') {
    return section.images;
  }
  return 'items' in section ? section.items : [];
}

export function canAdd(section: Section): boolean {
  const limit = ITEM_LIMITS[section.type] ?? IMAGE_LIMITS[section.type] ?? 0;
  return listOf(section).length < limit;
}

export function emptyImage(): ImageSlot {
  return { asset: null, alt: '' };
}

/** A blank entry for a section's list. */
export function newEntry(section: Section): unknown {
  switch (section.type) {
    case 'hero':
    case 'gallery':
      return emptyImage();
    case 'offerings':
      return { title: 'New item', text: '', image: null, tags: [], cta: null };
    case 'steps':
      return { title: 'New step', text: '', icon: 'check' };
    case 'people':
      return { name: 'Name', role: '', photo: null, facts: [] };
    case 'testimonials':
      return { quote: 'A few words.', name: 'Name', relation: '', rating: null, photo: null };
    case 'faq':
      return { q: 'A question?', a: 'The answer.' };
    default:
      return null;
  }
}

/** Every image slot gets the address it is served from, for the preview. */
export function withUrls<T>(content: T): T {
  const copy = structuredClone(content);
  const walk = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach(walk);
    } else if (value && typeof value === 'object') {
      const record = value as Record<string, unknown>;
      if ('asset' in record) {
        record['url'] = record['asset'] ? `/api/v1/public/assets/${record['asset']}` : null;
      }
      Object.values(record).forEach(walk);
    }
  };
  walk(copy);
  return copy;
}
