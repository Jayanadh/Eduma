export type NavItem = { label: string; icon: string; link: string };

const WORKSPACE: (NavItem & { needs?: string })[] = [
  { label: 'Home', icon: 'home', link: '/app' },
  { label: 'Staff', icon: 'users', link: '/app/staff', needs: 'membership.read' },
  { label: 'Roles', icon: 'key', link: '/app/roles', needs: 'role.manage' },
  { label: 'Organization', icon: 'building', link: '/app/organization', needs: 'organization.manage' },
  { label: 'Public site', icon: 'globe', link: '/app/site', needs: 'institution_brand.update' },
  { label: 'Profile', icon: 'user', link: '/app/profile' },
];

/** The sidebar: the console's pages on Eduma's address; on an institution's, the pages the member's roles open. */
export function navFor(kind: 'platform' | 'institution', can: (perm: string) => boolean): NavItem[] {
  return kind === 'platform'
    ? [
        { label: 'Overview', icon: 'grid', link: '/console' },
        { label: 'Institutions', icon: 'institution', link: '/console/institutions' },
        { label: 'Audit log', icon: 'list', link: '/console/audit' },
      ]
    : WORKSPACE.filter((item) => !item.needs || can(item.needs)).map(({ label, icon, link }) => ({ label, icon, link }));
}
