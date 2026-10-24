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
  /** Staff work in /app; applicants, students and guardians have their own portals. */
  kind: 'staff' | 'applicant' | 'student' | 'guardian';
  /** Colleges and universities get programs and courses in their menu; schools get grades. */
  category?: Category;
  /** Modules switched on here, for menus; the server gates every module route too. */
  modules_enabled?: string[];
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
  employee: { number: string; joined_on: string | null; left_on: string | null };
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

export type QuestionKind = 'text' | 'long_text' | 'date' | 'choice' | 'yes_no';
export type ApplicationStage =
  | 'draft'
  | 'submitted'
  | 'under_review'
  | 'needs_information'
  | 'eligible'
  | 'rejected'
  | 'offered'
  | 'offer_expired'
  | 'accepted'
  | 'enrolled'
  | 'withdrawn';

export type ApplicationDocument = {
  id: string;
  requirement: string;
  label: string;
  original_name: string;
  content_type: string;
  size: number;
  status: 'pending' | 'verified' | 'rejected' | 'replaced';
  uploaded_at: string;
  review_note?: string;
  version?: number;
};

/** An application as its applicant sees it. */
export type ApplicantApplication = {
  id: string;
  number: string;
  stage: ApplicationStage;
  stage_label: string;
  version: number;
  cycle: { id: string; name: string; academic_year: string; closes_on: string };
  place: { id: string; label: string; campus_name: string | null };
  questions: { code: string; label: string; help: string; kind: QuestionKind; options: string[]; required: boolean }[];
  requirements: { code: string; label: string; help: string; required: boolean }[];
  learner_name: string;
  date_of_birth: string | null;
  guardian_name: string;
  guardian_relationship: string;
  guardian_phone: string;
  guardian_email: string;
  address: string;
  previous_school: string;
  answers: Record<string, string | boolean | null>;
  information_request: string;
  decision_reason: string;
  offer_expires_on: string | null;
  submitted_at: string | null;
  documents: ApplicationDocument[];
  /** What still stops it being submitted: field → message. */
  missing: Record<string, string>;
  allowed_actions: ('edit' | 'upload' | 'submit' | 'withdraw' | 'accept')[];
};

export type CyclePlace = {
  id?: string;
  code: string;
  label: string;
  campus: { id: string; name: string } | null;
  seats: number;
  in_use?: number;
  /** A college place admits into a program. */
  program?: { id: string; code: string; name: string } | null;
};
export type CycleQuestion = { code: string; label: string; help: string; kind: QuestionKind; options: string[]; required: boolean };
export type CycleDocument = { code: string; label: string; help: string; required: boolean };

/** An admission cycle as staff see it. */
export type AdmissionCycle = {
  id: string;
  name: string;
  entry_year: number;
  academic_year: string;
  opens_on: string;
  closes_on: string;
  instructions: string;
  status: 'draft' | 'published' | 'closed';
  version: number;
  places: CyclePlace[];
  questions: CycleQuestion[];
  documents: CycleDocument[];
  counts: Partial<Record<ApplicationStage, number>>;
};

export type StaffApplicationItem = {
  id: string;
  number: string;
  stage: ApplicationStage;
  stage_label: string;
  learner_name: string;
  guardian_name: string;
  place: string;
  cycle: string;
  submitted_at: string | null;
};

/** An application as reviewing staff see it, with what they may do next. */
export type StaffApplication = Omit<ApplicantApplication, 'missing' | 'allowed_actions'> & {
  owner: { full_name: string; username: string };
  decided_by_name: string | null;
  submissions: { revision: number; submitted_at: string; snapshot: Record<string, unknown> }[];
  notes: { id: string; author: string; text: string; created_at: string }[];
  student_id: string | null;
  /** Existing students with the same name and date of birth: a warning, never a merge. */
  possible_duplicates: { id: string; number: string; full_name: string }[];
  actions: ('start_review' | 'request_information' | 'eligible' | 'reject' | 'offer' | 'enroll')[];
  can_review: boolean;
  can_approve: boolean;
};

export type StudentEnrollment = {
  academic_year: string;
  place_code: string;
  place_label: string;
  campus_name: string | null;
  entry_date: string;
  status: string;
  exit_date?: string | null;
  exit_reason?: string;
  program?: { id: string; code: string; name: string } | null;
  curriculum?: { id: string; label: string } | null;
};

export type StudentListItem = {
  id: string;
  number: string;
  full_name: string;
  status: string;
  enrollment: StudentEnrollment | null;
};

/** A student's record as staff with student.read see it. */
export type StudentRecord = StudentListItem & {
  version: number;
  date_of_birth: string | null;
  phone: string;
  email: string;
  address: string;
  admitted_on: string;
  enrollments: StudentEnrollment[];
  application: { id: string; number: string } | null;
  login: string | null;
  last_login: string | null;
  left_on: string | null;
  can_withdraw: boolean;
  can_reinstate: boolean;
  can_manage_guardians: boolean;
  can_change_program?: boolean;
  placements: Placement[];
  current_section: string | null;
};

/** A guardian link as staff see it; the evidence fields come only to those who manage links. */
export type GuardianLink = {
  id: string;
  version: number;
  adult: { full_name: string; phone: string; email: string };
  relationship: string;
  status: 'proposed' | 'active' | 'revoked';
  status_label: string;
  in_effect: boolean;
  access: { record: boolean; fees: boolean; messages: boolean };
  starts_on: string | null;
  ends_on: string | null;
  has_login: boolean;
  source: 'enrollment' | 'staff';
  needs_adult_review: boolean;
  restrictions?: string;
  authority_basis?: string;
  verification_method?: string;
  verification_reference?: string;
  revoke_reason?: string;
};

export type HistoryEntry = {
  at: string;
  actor: string | null;
  action: string;
  summary: string;
  changes: Record<string, unknown>;
};

/** What students see of their own record. */
export type OwnStudentRecord = Pick<
  StudentRecord,
  'number' | 'full_name' | 'date_of_birth' | 'status' | 'enrollment' | 'current_section'
>;

/** A child as their guardian sees them: the number and class only when the school shares the record. */
export type FamilyChild = {
  id: string;
  full_name: string;
  shared: boolean;
  number?: string;
  status?: string;
  left_on?: string | null;
  enrollment?: StudentEnrollment | null;
  current_section?: string | null;
};

export type EnquiryStatus = 'open' | 'following_up' | 'converted' | 'closed';

export type Enquiry = {
  id: string;
  version: number;
  number: string;
  contact_name: string;
  phone: string;
  email: string;
  learner_name: string;
  learner_date_of_birth: string | null;
  place: { id: string; label: string } | null;
  message: string;
  source: string;
  source_label: string;
  status: EnquiryStatus;
  status_label: string;
  close_reason: string;
  assigned_to: { id: string; full_name: string } | null;
  next_follow_up_on: string | null;
  application: { id: string; number: string } | null;
  created_at: string;
  created_by: { id: string; full_name: string } | null;
  follow_ups?: {
    how: string;
    how_label: string;
    note: string;
    at: string;
    author: string;
    next_follow_up_on: string | null;
  }[];
};

export type EnquiryPageResult = Page<Enquiry> & {
  summary: { status: Partial<Record<EnquiryStatus, number>>; source: Record<string, number> };
};

export type ImportJob = {
  id: string;
  version: number;
  source_system: string;
  original_name: string;
  status: 'validated' | 'committed' | 'discarded' | 'undone';
  status_label: string;
  totals: Record<string, number>;
  undecided: number;
  created_at: string;
  created_by: string | null;
  committed_at: string | null;
  /** Why a committed import can no longer be undone; null when it can. */
  undo_blocker?: string | null;
};

export type ImportRow = {
  id: string;
  row_number: number;
  source_record_id: string;
  full_name: string;
  state: 'valid' | 'error' | 'duplicate' | 'unchanged' | 'changed';
  state_label: string;
  errors: { field: string; code: string; message: string }[];
  duplicate_of: { kind: 'student' | 'row'; id?: string; row_number?: number; label: string }[];
  decision: '' | 'create' | 'skip';
  student: { id: string; number: string } | null;
};

export type Term = { id: string; name: string; ordinal: number; starts_on: string; ends_on: string };

export type AcademicYear = {
  id: string;
  version: number;
  code: string;
  starts_on: string;
  ends_on: string;
  status: 'planned' | 'current' | 'closed';
  status_label: string;
  terms: Term[];
};

export type Grade = { id: string; version: number; code: string; name: string; order: number; is_active: boolean };
export type Subject = { id: string; version: number; code: string; name: string; is_active: boolean };

export type SectionTeacher = {
  id: string;
  membership: { id: string; full_name: string };
  subject: { id: string; name: string } | null;
  starts_on: string;
  ends_on: string | null;
  in_effect: boolean;
};

export type ClassSection = {
  id: string;
  version: number;
  code: string;
  capacity: number;
  placed: number;
  year: { id: string; code: string; status: string };
  /** A school class names a grade; a college batch names a program instead. */
  grade: { id: string; name: string } | null;
  program: { id: string; code: string; name: string } | null;
  /** The grade's or the program's name. */
  level: string;
  campus: { id: string; name: string };
  class_teacher: { id: string; full_name: string } | null;
  teachers: SectionTeacher[];
  can_manage: boolean;
};

export type RosterRow = {
  period: string;
  student: { id: string; number: string; full_name: string };
  status: string;
  is_repeat: boolean;
};

export type MoveUpRow = {
  student: { id: string; number: string; full_name: string };
  action: 'move' | 'already_placed' | 'withdrawn' | 'not_enrolled';
};

export type TeachingClass = {
  /** One of the two: a class or batch, or a course offering (whose class list arrives with registration). */
  section?: { id: string; code: string; grade: string; year: string };
  offering?: { id: string; course: string; title: string; code: string; term: string; year: string };
  subjects: string[];
  class_teacher: boolean;
};

export type Placement = { year: string; grade: string; section: string; campus: string; state: string; is_repeat: boolean };

export type Program = {
  id: string;
  version: number;
  code: string;
  name: string;
  qualification: string;
  length_terms: number;
  department: Named | null;
  is_active: boolean;
  can_manage: boolean;
};

export type Course = {
  id: string;
  version: number;
  code: string;
  title: string;
  credits: string;
  kind: 'theory' | 'lab' | 'project' | 'tutorial' | 'other';
  kind_label: string;
  department: Named | null;
  is_active: boolean;
  can_manage: boolean;
};

export type CurriculumSummary = {
  id: string;
  version: number;
  regulation: string;
  revision: number;
  cohort: number;
  credits_required: string;
  status: 'draft' | 'published' | 'retired';
  status_label: string;
  published_at: string | null;
};

export type CurriculumEntry = {
  id: string;
  course: { id: string; code: string; title: string; credits: string; kind: string };
  category: string;
  category_label: string;
  term: number;
  elective_group: string;
  /** Course codes. */
  prerequisites: string[];
};

export type Curriculum = CurriculumSummary & {
  program: { id: string; code: string; name: string; length_terms: number };
  total_credits: string;
  terms: { term: number; courses: CurriculumEntry[] }[];
  can_manage: boolean;
};

export type OfferingTeacher = {
  id: string;
  membership: { id: string; full_name: string };
  starts_on: string;
  ends_on: string | null;
  in_effect: boolean;
};

export type Offering = {
  id: string;
  version: number;
  /** PHY101-A */
  label: string;
  code: string;
  capacity: number;
  status: 'planned' | 'open' | 'closed' | 'cancelled';
  status_label: string;
  course: { id: string; code: string; title: string; credits: string };
  term: { id: string; name: string; year: string; year_status: string };
  campus: Named;
  linked_to: { id: string; label: string } | null;
  linked: string[];
  teachers: OfferingTeacher[];
  can_manage: boolean;
};
