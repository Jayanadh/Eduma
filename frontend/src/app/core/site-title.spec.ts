import { siteTitle } from './site-title';

describe('siteTitle', () => {
  it('puts the page before the site name', () => {
    expect(siteTitle('Institutions', 'Eduma')).toBe('Institutions · Eduma');
    expect(siteTitle(undefined, 'Aster School')).toBe('Aster School');
  });
});
