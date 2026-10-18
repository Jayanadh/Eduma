export type NavItem = { label: string; icon: string; link: string; group?: 'People' | 'Administration' };

/** `needs`: the permission, or any one of several, that opens the page. */
const WORKSPACE: (NavItem & { needs?: string | string[] })[] = [
  { label: 'Home', icon: 'home', link: '/app' },
  { label: 'Staff', icon: 'users', link: '/app/staff', group: 'People', needs: 'membership.read' },
  { label: 'Roles', icon: 'key', link: '/app/roles', group: 'People', needs: 'role.manage' },
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
  { label: 'Public site', icon: 'globe', link: '/app/site', group: 'Administration', needs: 'institution_brand.update' },
  { label: 'Profile', icon: 'user', link: '/app/profile', group: 'Administration' },
];

/**
 * The sidebar: the console's pages on Eduma's address; on an institution's, the pages the member's roles open, under
 * at most three headings (spec pack 04 §1: six or fewer top-level groups).
 */
export function navFor(kind: 'platform' | 'institution', can: (perm: string) => boolean): NavItem[] {
  return kind === 'platform'
    ? [
        { label: 'Overview', icon: 'grid', link: '/console' },
        { label: 'Institutions', icon: 'institution', link: '/console/institutions' },
        { label: 'Audit log', icon: 'list', link: '/console/audit' },
      ]
    : WORKSPACE.filter((item) => !item.needs || [item.needs].flat().some(can)).map(({ needs, ...item }) => item);
}
