import { defaultsFor, tick, untick } from './modules';
import { MODULE_CATALOGUE } from './test-data';

describe('module choices', () => {
  it('ticking a module ticks what it needs, all the way down', () => {
    expect(tick([], 'report_cards', MODULE_CATALOGUE)).toEqual(['academics', 'exams', 'report_cards']);
    expect(tick(['library'], 'fees', MODULE_CATALOGUE)).toEqual(['fees', 'library', 'students']);
  });

  it('unticking a module unticks everything that needs it', () => {
    const all = MODULE_CATALOGUE.map((module) => module.key);
    expect(untick(all, 'academics', MODULE_CATALOGUE)).toEqual([
      'admissions',
      'communication',
      'fees',
      'library',
      'reports',
      'students',
    ]);
  });

  it('starts each category from its defaults', () => {
    expect(defaultsFor('school', MODULE_CATALOGUE)).toContain('report_cards');
    expect(defaultsFor('school', MODULE_CATALOGUE)).not.toContain('course_registration');
    expect(defaultsFor('university', MODULE_CATALOGUE)).toContain('affiliations');
    expect(defaultsFor('college', MODULE_CATALOGUE)).not.toContain('library');
  });
});
