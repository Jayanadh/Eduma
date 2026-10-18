import { navFor } from './nav';

const holding = (...perms: string[]) => (perm: string) => perms.includes(perm);

describe('navFor', () => {
  it('shows a member without staff permissions only Home and Profile', () => {
    expect(navFor('institution', holding('institution.read')).map((item) => item.label)).toEqual(['Home', 'Profile']);
  });

  it('adds Staff for people who can see staff', () => {
    expect(navFor('institution', holding('membership.read')).map((item) => item.label)).toEqual([
      'Home',
      'Staff',
      'Profile',
    ]);
  });

  it('gives an Institution Admin every workspace page, in order', () => {
    const admin = holding(
      'membership.read',
      'role.manage',
      'organization.manage',
      'institution_brand.update',
    );
    expect(navFor('institution', admin).map((item) => item.link)).toEqual([
      '/app',
      '/app/staff',
      '/app/roles',
      '/app/organization',
      '/app/site',
      '/app/profile',
    ]);
  });

  it('keeps the console pages for the platform', () => {
    expect(navFor('platform', holding()).map((item) => item.label)).toEqual(['Overview', 'Institutions', 'Audit log']);
  });
});
