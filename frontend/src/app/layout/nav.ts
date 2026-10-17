export type NavItem = { label: string; icon: string; link: string };

/** The sidebar: the console's pages on Eduma's address, the workspace's on an institution's. */
export function navFor(kind: 'platform' | 'institution'): NavItem[] {
  return kind === 'platform'
    ? [
        { label: 'Overview', icon: 'grid', link: '/console' },
        { label: 'Institutions', icon: 'institution', link: '/console/institutions' },
        { label: 'Audit log', icon: 'list', link: '/console/audit' },
      ]
    : [
        { label: 'Home', icon: 'home', link: '/app' },
        { label: 'Public site', icon: 'globe', link: '/app/site' },
        { label: 'Profile', icon: 'building', link: '/app/profile' },
      ];
}
