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

  it('gives an Institution Admin every workspace page, grouped, in order', () => {
    const admin = holding(
      'membership.read',
      'role.manage',
      'organization.manage',
      'configuration.edit',
      'institution_brand.update',
    );
    expect(navFor('institution', admin).map((item) => [item.group ?? '', item.label])).toEqual([
      ['', 'Home'],
      ['People', 'Staff'],
      ['People', 'Roles'],
      ['Administration', 'Organization'],
      ['Administration', 'Settings'],
      ['Administration', 'Public site'],
      ['Administration', 'Profile'],
    ]);
  });

  it('keeps the console pages for the platform', () => {
    expect(navFor('platform', holding()).map((item) => item.label)).toEqual(['Overview', 'Institutions', 'Affiliations', 'Audit log']);
  });

  it('opens Settings to someone who only approves setting changes', () => {
    expect(navFor('institution', holding('configuration.publish')).map((item) => item.label)).toContain('Settings');
  });

  it('shows the Admissions pages only when the module is switched on', () => {
    const can = holding('admission_cycle.manage', 'application.review', 'student.read');
    expect(navFor('institution', can, () => false).map((item) => item.label)).not.toContain('Applications');
    const on = navFor('institution', can, (module) => ['admissions', 'students'].includes(module));
    expect(on.filter((item) => item.group === 'Admissions').map((item) => item.label)).toEqual(['Cycles', 'Applications']);
    expect(on.map((item) => item.label)).toContain('Students');
  });

  it('shows Programs, Courses and Offerings to colleges and universities, not schools', () => {
    const can = holding('academic_structure.manage');
    const academics = (higher: boolean) =>
      navFor('institution', can, (module) => module === 'academics', higher)
        .filter((item) => item.group === 'Academics')
        .map((item) => item.label);
    expect(academics(false)).toEqual(['Academic setup', 'Sections', 'Timetable', 'My classes']);
    expect(academics(true)).toEqual(['Academic setup', 'Sections', 'Timetable', 'Programs', 'Courses', 'Offerings', 'My classes']);
  });
});
