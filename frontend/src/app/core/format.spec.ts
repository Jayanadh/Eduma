import { date, dateTime, joined, money, number, readable } from './format';

describe('format', () => {
  it('formats dates as a day in India', () => {
    expect(date('2026-10-05')).toBe('05 Oct 2026');
    expect(date('2026-10-04T20:00:00Z')).toBe('05 Oct 2026');
    expect(date(null)).toBe('—');
  });

  it('formats moments in India time', () => {
    expect(dateTime('2026-10-17T04:30:00Z')).toBe('17 Oct 2026, 10:00 am');
  });

  it('formats numbers the Indian way', () => {
    expect(number(123456)).toBe('1,23,456');
    expect(number(null)).toBe('—');
  });

  it('formats money in rupees with Indian grouping', () => {
    expect(money('7400000.50')).toBe('₹74,00,000.50');
    expect(money(3000)).toBe('₹3,000.00');
    expect(money(null)).toBe('—');
    expect(money('n/a')).toBe('n/a');
  });

  it('joins only the parts that exist', () => {
    expect(joined('Laboratory', '', null, false, 'bookable')).toBe('Laboratory · bookable');
    expect(joined()).toBe('');
  });

  it('makes codes readable', () => {
    expect(readable('engineering_college')).toBe('Engineering college');
    expect(readable(null)).toBe('—');
  });
});
