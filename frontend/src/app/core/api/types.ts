/** The shapes the API returns (see the backend serializers). */

export type SiteKind = 'platform' | 'institution' | 'unknown';
export type Category = 'school' | 'college' | 'engineering_college' | 'university';
export type LifecycleStatus = 'setup' | 'active' | 'suspended' | 'archived';

export type Me = {
  id: string;
  username: string;
  full_name: string;
  email: string;
  is_platform_admin: boolean;
  must_change_password: boolean;
  membership: { role: string; permissions: string[] } | null;
};

/** The four stored theme fields plus the readable colours the server derives from them. */
export type Theme = {
  primary_color: string;
  secondary_color: string;
  heading_font: string;
  body_font: string;
  /** What text sits on: the colour itself, or a little darker for mid-tones so text stays readable. */
  primary_fill: string;
  secondary_fill: string;
  on_primary: string;
  primary_text: string;
  on_secondary: string;
  secondary_text: string;
};

export type StoredTheme = Pick<Theme, 'primary_color' | 'secondary_color' | 'heading_font' | 'body_font'>;

export type Cta = { label: string; href: string };
/** An image slot: `asset` is null for an empty slot; `url` is added by the public API only. */
export type ImageSlot = { asset: string | null; alt: string; url?: string | null };

type SectionBase = { id: string; visible: boolean; eyebrow: string; title: string };

export type HeroSection = SectionBase & {
  type: 'hero';
  subtitle: string;
  primary_cta: Cta;
  secondary_cta: Cta | null;
  images: ImageSlot[];
  badge: { value: string; label: string } | null;
  stickers: string[];
};
export type OfferingsSection = SectionBase & {
  type: 'offerings';
  subtitle: string;
  items: { title: string; text: string; image: ImageSlot | null; tags: string[]; cta: Cta | null }[];
};
export type StepsSection = SectionBase & {
  type: 'steps';
  items: { title: string; text: string; icon: string }[];
};
export type PeopleSection = SectionBase & {
  type: 'people';
  subtitle: string;
  items: { name: string; role: string; photo: ImageSlot | null; facts: string[] }[];
};
export type GallerySection = SectionBase & { type: 'gallery'; images: ImageSlot[] };
export type TestimonialsSection = SectionBase & {
  type: 'testimonials';
  items: { quote: string; name: string; relation: string; rating: number | null; photo: ImageSlot | null }[];
};
export type FeatureSection = SectionBase & {
  type: 'feature';
  text: string;
  bullets: string[];
  image: ImageSlot | null;
  cta: Cta | null;
};
export type FaqSection = SectionBase & {
  type: 'faq';
  subtitle: string;
  cta: Cta | null;
  items: { q: string; a: string }[];
};

export type Section =
  | HeroSection
  | OfferingsSection
  | StepsSection
  | PeopleSection
  | GallerySection
  | TestimonialsSection
  | FeatureSection
  | FaqSection;
export type SectionType = Section['type'];
export type SiteContent = { sections: Section[] };

export type PublicInstitution = {
  slug: string;
  display_name: string;
  category: Category;
  contact_email: string;
  contact_phone: string;
  address: string;
};

/** GET /api/v1/public/site: what the current address shows. */
export type PublicSite =
  | { kind: 'platform'; theme: Theme; content: SiteContent; logo_url: string | null }
  | {
      kind: 'institution';
      mode: 'full' | 'opening_soon';
      institution: PublicInstitution;
      theme: Theme;
      content: SiteContent;
      logo_url: string | null;
    }
  | { kind: 'institution'; mode: 'unavailable'; institution: { display_name: string } };

export type Revision = {
  id: string;
  number: number;
  status: 'draft' | 'published' | 'superseded';
  version: number;
  theme: Theme;
  logo: { id: string; url: string } | null;
  content: SiteContent;
  created_at: string;
  published_at: string | null;
  published_by_name: string | null;
};
export type RevisionListItem = Pick<
  Revision,
  'id' | 'number' | 'status' | 'created_at' | 'published_at' | 'published_by_name'
>;
export type UploadedAsset = { id: string; url: string; width: number; height: number };

export type ReadinessItem = { code: string; label: string; done: boolean };

export type InstitutionListItem = {
  id: string;
  display_name: string;
  slug: string;
  url: string;
  category: Category;
  lifecycle_status: LifecycleStatus;
  created_at: string;
  ready: boolean;
};

export type InstitutionDetail = {
  id: string;
  slug: string;
  legal_name: string;
  display_name: string;
  category: Category;
  country_code: string;
  timezone: string;
  base_currency: string;
  contact_email: string;
  contact_phone: string;
  address: string;
  board_affiliation_code: string;
  udise_code: string;
  aishe_code: string;
  url: string;
  lifecycle_status: LifecycleStatus;
  status_reason: string;
  activated_at: string | null;
  created_at: string;
  version: number;
  readiness: ReadinessItem[];
  admin?: {
    id: string;
    username: string;
    full_name: string;
    must_change_password: boolean;
    last_login: string | null;
  } | null;
};

export type Overview = {
  counts: Record<LifecycleStatus, number>;
  needs_action: { id: string; display_name: string; slug: string; missing: string[] }[];
};

export type AuditItem = {
  id: string;
  at: string;
  actor_name: string | null;
  institution_name: string | null;
  action: string;
  summary: string;
  changes: Record<string, unknown>;
};

/** A page of a long list (Django REST framework page-number pagination). */
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export const CATEGORY_LABELS: Readonly<Record<Category, string>> = {
  school: 'School',
  college: 'College',
  engineering_college: 'Engineering college',
  university: 'University',
};
