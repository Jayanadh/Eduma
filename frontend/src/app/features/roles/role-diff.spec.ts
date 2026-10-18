import { roleDiff } from './role-diff';

describe('roleDiff', () => {
  it('names what a change adds and removes', () => {
    expect(roleDiff(['a', 'b'], ['b', 'c'])).toEqual({ added: ['c'], removed: ['a'] });
    expect(roleDiff(['b', 'a'], ['a', 'b'])).toEqual({ added: [], removed: [] });
  });
});
