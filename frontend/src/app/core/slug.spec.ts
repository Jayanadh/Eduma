import { slugify } from './slug';

describe('slugify', () => {
  it('makes a web address from a name', () => {
    expect(slugify('Aster School, Vijayawada')).toBe('aster-school-vijayawada');
    expect(slugify("  St. Mary's  ")).toBe('st-marys');
    expect(slugify('A -- B')).toBe('a-b');
  });

  it('drops letters a web address cannot hold', () => {
    expect(slugify('श्री विद्या')).toBe('');
    expect(slugify('श्री Vidya Niketan')).toBe('vidya-niketan');
  });

  it('keeps within 40 characters and never ends on a dash', () => {
    expect(slugify('a'.repeat(60))).toHaveLength(40);
    expect(slugify(`${'a'.repeat(39)} b`)).toBe('a'.repeat(39));
    expect(slugify('ab')).toBe('');
  });
});
