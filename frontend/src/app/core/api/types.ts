/** The shapes the API returns (see the backend serializers). */

export type SiteKind = 'platform' | 'institution' | 'unknown';
export type Category = 'school' | 'college' | 'engineering_college' | 'university';
export type LifecycleStatus = 'setup' | 'active' | 'restricted' | 'suspended' | 'archived';

export type Me = {
  id: string;
  username: string;
  full_name: string;
  email: string;
  is_platform_admin: boolean;
  must_change_password: boolean;
  membership: Membership | null;
};

/** The signed-in person's place in this address's institution. Permissions are for menus; the server checks scope. */
export type Membership = {
  /** Staff work in /app; applicants and students have their own portals. */
  kind: 'staff' | 'applicant' | 'student';
  roles: RoleLine[];
  permissions: string[];
  /** The institution is read-only for now; status_reason says why. */
  restricted: boolean;
  status_reason: string;
};

export type RoleLine = { label: string; scope_label: string };
export type ScopeType = 'institution' | 'campus' | 'department';
type Named = { id: string; name: string };

export type Campus = { id: string; code: string; name: string; address: string; is_active: boolean; version: number };
export type Department = {
  id: string;
  code: string;
  name: string;
  campus: Named | null;
  parent: Named | null;
  is_active: boolean;
  version: number;
};

export type PermissionInfo = { name: string; label: string; institution_only: boolean };
export type PermissionGroup = { group: string; permissions: PermissionInfo[] };

/** A built-in role (id is its key, version null) or one of the institution's custom roles. */
export type RoleItem = {
  id: string;
  builtin: boolean;
  label: string;
  description: string;
  permissions: string[];
  assigned_count: number;
  is_active: boolean;
  version: number | null;
};

export type StaffItem = { id: string; full_name: string; username: string; status: 'active' | 'revoked'; roles: RoleLine[] };
export type Assignment = {
  id: string;
  role_label: string;
  scope_type: ScopeType;
  scope_label: string;
  starts_on: string;
  ends_on: string | null;
  status: 'active' | 'pending' | 'ended';
  end_reason: string;
  in_effect: boolean;
  /** On the institution's own calendar: in effect, waiting for approval, starting later, or ended. */
  phase: 'now' | 'waiting' | 'later' | 'earlier';
  requested_by_name: string | null;
  /** The viewer may approve or reject this waiting role. */
  can_decide: boolean;
};

/** What waits for the signed-in member's decision. */
export type Approvals = {
  roles: {
    staff_id: string;
    assignment_id: string;
    person: string;
    role_label: string;
    scope_label: string;
    requested_by_name: string | null;
    requested_at: string;
  }[];
  settings: { key: string; label: string; revision_id: string; submitted_by_name: string | null; description: string }[];
};
export type StaffDetail = StaffItem & {
  email: string;
  mobile: string;
  last_login: string | null;
  must_change_password: boolean;
  version: number;
  assignments: Assignment[];
  can_manage: boolean;
  /** The viewer may give this person roles (each role and place is checked when sent). */
  can_give: boolean;
};

export type ModuleInfo = {
  key: string;
  label: string;
  group: 'core' | 'operations';
  depends_on: string[];
  default_for: Category[];
  available: boolean;
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
  /** A domain the institution owns, e.g. www.dps.edu.in; '' when it uses its Eduma address. */
  custom_domain: string;
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
  /** Module keys the institution's plan includes. */
  modules: string[];
  /** Of those, the ones switched on in its settings (institution's own view only). */
  modules_enabled?: string[];
  academic_year?: { label: string; starts_on: string; ends_on: string };
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

export type SettingKind = 'modules' | 'bool' | 'month';

/** One version of a setting: a draft, a change waiting for approval, or history. */
export type SettingRevisionItem = {
  id: string;
  number: number;
  status: 'draft' | 'pending' | 'published' | 'superseded' | 'withdrawn';
  version: number;
  value: unknown;
  description: string;
  effective_from: string | null;
  reason: string;
  return_note: string;
  created_by_name: string | null;
  submitted_by_name: string | null;
  submitted_at: string | null;
  approved_by_name: string | null;
  published_at: string | null;
  /** The viewer sent this change. */
  mine: boolean;
  can_approve: boolean;
};

export type SettingSummary = {
  key: string;
  label: string;
  help: string;
  kind: SettingKind;
  needs_approval: boolean;
  value_now: unknown;
  description_now: string;
  scheduled: { effective_from: string; description: string } | null;
  open: { id: string; status: 'draft' | 'pending'; version: number } | null;
};

export type SettingDetail = SettingSummary & {
  draft: SettingRevisionItem | null;
  pending: SettingRevisionItem | null;
  preview: string[];
  choices: { key: string; label: string; group: 'core' | 'operations'; depends_on: string[] }[];
  history: { count: number; results: SettingRevisionItem[] };
};

/** What anyone may see of an institution's admissions. */
export type PublicAdmissions = {
  open: boolean;
  cycles: {
    id: string;
    name: string;
    academic_year: string;
    opens_on: string;
    closes_on: string;
    instructions: string;
    places: { id: string; label: string; campus_name: string | null }[];
    documents: { code: string; label: string; required: boolean }[];
  }[];
};
