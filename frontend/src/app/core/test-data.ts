import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Category, Me, ModuleInfo, PublicSite, Theme } from './api/types';
import { AuthStore } from './auth-store';
import { SiteStore } from './site-store';

export const EDUMA_THEME: Theme = {
  primary_color: '#4B5AE4',
  secondary_color: '#FFD43B',
  primary_fill: '#4B5AE4',
  secondary_fill: '#FFD43B',
  heading_font: 'bricolage',
  body_font: 'dm-sans',
  on_primary: '#FFFFFF',
  primary_text: '#4B5AE4',
  on_secondary: '#17132B',
  secondary_text: '#8D6E00',
};

/** An Institution Admin by default; override only what a test cares about. */
export function makeMe(overrides: Partial<Me> = {}): Me {
  return {
    id: 'u-1',
    username: 'aster.admin',
    full_name: 'Asha Rao',
    email: '',
    is_platform_admin: false,
    must_change_password: false,
    membership: {
      roles: [{ label: 'Institution Admin', scope_label: 'Whole institution' }],
      permissions: [
        'institution.read',
        'institution_brand.update',
        'institution_profile.update',
        'membership.assign',
        'membership.read',
        'organization.manage',
        'role.manage',
      ],
      restricted: false,
      status_reason: '',
    },
    ...overrides,
  };
}

export const PLATFORM_ADMIN = makeMe({
  username: 'eduma.admin',
  full_name: 'Eduma Platform Admin',
  is_platform_admin: true,
  membership: null,
});

export function makeSite(kind: 'platform' | 'institution', overrides: object = {}): PublicSite {
  const content = {
    sections: [
      {
        id: 'hero',
        type: 'hero' as const,
        visible: true,
        eyebrow: 'Admissions open',
        title: 'Welcome to Aster School',
        subtitle: '',
        primary_cta: { label: 'Visit', href: '#s-faq' },
        secondary_cta: null,
        images: [],
        badge: null,
        stickers: [],
      },
    ],
  };
  if (kind === 'platform') {
    return { kind, theme: EDUMA_THEME, content, logo_url: '/eduma-logo.png', ...overrides } as PublicSite;
  }
  return {
    kind,
    mode: 'full',
    institution: {
      slug: 'aster',
      display_name: 'Aster School',
      category: 'school',
      contact_email: 'office@aster.example',
      contact_phone: '+91 90000 00001',
      address: '1 Lake Road',
    },
    theme: { ...EDUMA_THEME, primary_color: '#5B3FD9', primary_fill: '#5B3FD9', heading_font: 'fredoka', body_font: 'nunito' },
    content,
    logo_url: null,
    ...overrides,
  } as PublicSite;
}

/** Loads `site` into SiteStore through its real call. Needs provideHttpClientTesting(). */
export async function onSite(site: PublicSite | null): Promise<void> {
  const loaded = TestBed.inject(SiteStore).load();
  const request = TestBed.inject(HttpTestingController).expectOne('/api/v1/public/site');
  if (site) {
    request.flush(site);
  } else {
    request.flush({ code: 'not_found' }, { status: 404, statusText: 'Not Found' });
  }
  await loaded;
}

/** Puts `user` (or nobody) into AuthStore through its real session call. Needs provideHttpClientTesting(). */
export async function signInAs(user: Me | null): Promise<void> {
  const loaded = TestBed.inject(AuthStore).loadSession();
  TestBed.inject(HttpTestingController).expectOne('/api/v1/session').flush({ user });
  await loaded;
}

const ALL: Category[] = ['college', 'engineering_college', 'school', 'university'];
const HIGHER: Category[] = ['college', 'engineering_college', 'university'];

/** The module catalogue as GET /api/v1/platform/modules sends it (backend institutions/modules.py). */
export const MODULE_CATALOGUE: ModuleInfo[] = (
  [
    ['admissions', 'Admissions and enrollment', 'core', ['students'], ALL],
    ['students', 'Students and guardians', 'core', [], ALL],
    ['academics', 'Academic structure and timetable', 'core', [], ALL],
    ['attendance', 'Attendance', 'core', ['academics'], ALL],
    ['exams', 'Assessment and results', 'core', ['academics'], ALL],
    ['report_cards', 'Grades, sections, report cards and promotion', 'core', ['exams'], ['school']],
    ['course_registration', 'Course registration, credits and degree audit', 'core', ['academics'], HIGHER],
    ['outcomes', 'Lab batches, projects and outcome evidence', 'core', ['exams'], ['engineering_college', 'university']],
    ['affiliations', 'Affiliated colleges and central examinations', 'core', ['exams'], ['university']],
    ['fees', 'Fees', 'core', ['students'], ALL],
    ['communication', 'Messages, calls and online classes', 'core', ['students'], ALL],
    ['reports', 'Reports', 'core', [], ALL],
    ['library', 'Library', 'operations', [], []],
  ] as const
).map(([key, label, group, depends_on, default_for]) => ({
  key,
  label,
  group,
  depends_on: [...depends_on],
  default_for: [...default_for],
  available: false,
}));
