import { navFor } from './nav';

describe('navFor', () => {
  it('gives the console its pages', () =>
    expect(navFor('platform').map((item) => item.link)).toEqual([
      '/console',
      '/console/institutions',
      '/console/audit',
    ]));

  it('gives an institution its workspace pages', () =>
    expect(navFor('institution').map((item) => item.link)).toEqual(['/app', '/app/site', '/app/profile']));
});
