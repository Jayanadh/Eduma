export type NavItem = {
  label: string;
  icon: string;
  link: string;
  group?: 'People' | 'Admissions' | 'Academics' | 'Administration';
};

/**
 * `needs`: the permission, or any one of several, that opens the page; `module`: shown only while it is on;
 * `higher`: only for colleges and universities (programs and courses), not schools.
 */
const WORKSPACE: (NavItem & { needs?: string | string[]; module?: string; higher?: boolean })[] = [
  { label: 'Home', icon: 'home', link: '/app' },
  { label: 'Students', icon: 'graduation', link: '/app/students', group: 'People', needs: 'student.read', module: 'students' },
  { label: 'Staff', icon: 'users', link: '/app/staff', group: 'People', needs: 'membership.read' },
  { label: 'Roles', icon: 'key', link: '/app/roles', group: 'People', needs: 'role.manage' },
  {
    label: 'Cycles',
    icon: 'calendar',
    link: '/app/admissions/cycles',
    group: 'Admissions',
    needs: 'admission_cycle.manage',
    module: 'admissions',
  },
  {
    label: 'Enquiries',
    icon: 'message',
    link: '/app/admissions/enquiries',
    group: 'Admissions',
    needs: 'enquiry.manage',
    module: 'admissions',
  },
  {
    label: 'Applications',
    icon: 'file-text',
    link: '/app/admissions/applications',
    group: 'Admissions',
    needs: ['application.review', 'admission.approve'],
    module: 'admissions',
  },
  {
    label: 'Academic setup',
    icon: 'calendar',
    link: '/app/academics/setup',
    group: 'Academics',
    needs: 'academic_structure.manage',
    module: 'academics',
  },
  {
    label: 'Sections',
    icon: 'layers',
    link: '/app/academics/sections',
    group: 'Academics',
    needs: 'academic_structure.manage',
    module: 'academics',
  },
  {
    label: 'Programs',
    icon: 'award',
    link: '/app/academics/programs',
    group: 'Academics',
    needs: 'academic_structure.manage',
    module: 'academics',
    higher: true,
  },
  {
    label: 'Courses',
    icon: 'book-open',
    link: '/app/academics/courses',
    group: 'Academics',
    needs: 'academic_structure.manage',
    module: 'academics',
    higher: true,
  },
  {
    label: 'Offerings',
    icon: 'clipboard',
    link: '/app/academics/offerings',
    group: 'Academics',
    needs: 'academic_structure.manage',
    module: 'academics',
    higher: true,
  },
  {
    label: 'Affiliations',
    icon: 'external',
    link: '/app/affiliations',
    group: 'Academics',
    needs: ['affiliation.submit', 'affiliation.review'],
    module: 'academics',
    higher: true,
  },
  { label: 'My classes', icon: 'book', link: '/app/teaching', group: 'Academics', module: 'academics' },
  {
    label: 'Organization',
    icon: 'building',
    link: '/app/organization',
    group: 'Administration',
    needs: 'organization.manage',
  },
  {
    label: 'Settings',
    icon: 'layers',
    link: '/app/settings',
    group: 'Administration',
    needs: ['configuration.edit', 'configuration.publish'],
  },
  {
    label: 'Data transfer',
    icon: 'upload',
    link: '/app/data',
    group: 'Administration',
    needs: 'data.import',
    module: 'students',
  },
  { label: 'Public site', icon: 'globe', link: '/app/site', group: 'Administration', needs: 'institution_brand.update' },
  { label: 'Profile', icon: 'user', link: '/app/profile', group: 'Administration' },
];

/**
 * The sidebar: the console's pages on Eduma's address; on an institution's, the pages the member's roles open, under
 * at most four headings (spec pack 04 §1: six or fewer top-level groups).
 */
export function navFor(
  kind: 'platform' | 'institution',
  can: (perm: string) => boolean,
  on: (module: string) => boolean = () => false,
  higher = false,
): NavItem[] {
  return kind === 'platform'
    ? [
        { label: 'Overview', icon: 'grid', link: '/console' },
        { label: 'Institutions', icon: 'institution', link: '/console/institutions' },
        { label: 'Affiliations', icon: 'external', link: '/console/affiliations' },
        { label: 'Audit log', icon: 'list', link: '/console/audit' },
      ]
    : WORKSPACE.filter(
        (item) =>
          (!item.needs || [item.needs].flat().some(can)) && (!item.module || on(item.module)) && (!item.higher || higher),
      ).map(({ needs, module, higher, ...item }) => item);
}
