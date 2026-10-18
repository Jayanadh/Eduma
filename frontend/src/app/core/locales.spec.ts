import { COUNTRIES, CURRENCIES, TIME_ZONES, withCurrent } from './locales';

describe('locale choices', () => {
  it('lists real countries by name, without groupings or retired codes', () => {
    const codes = COUNTRIES.map((choice) => choice.code);
    expect(COUNTRIES.find((choice) => choice.code === 'IN')?.label).toBe('India');
    expect(codes).not.toContain('EU');
    expect(codes).not.toContain('SU');
    expect(codes.length).toBeGreaterThan(240);
  });

  it('lists currencies with their names and zones by their current names', () => {
    expect(CURRENCIES.find((choice) => choice.code === 'INR')?.label).toBe('INR · Indian Rupee');
    const zones = TIME_ZONES.map((choice) => choice.code);
    expect(zones).toContain('Asia/Kolkata');
    expect(zones).not.toContain('Asia/Calcutta');
  });

  it('keeps a saved value the list does not have', () => {
    expect(withCurrent(TIME_ZONES, 'Asia/Kolkata')).toBe(TIME_ZONES);
    expect(withCurrent(TIME_ZONES, 'Etc/GMT+5')[0]).toEqual({ code: 'Etc/GMT+5', label: 'Etc/GMT+5' });
  });
});
