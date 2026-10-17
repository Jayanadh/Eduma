const LOCALE = 'en-IN';
const TIME_ZONE = 'Asia/Kolkata';
const NO_VALUE = '—';

const NUMBER = new Intl.NumberFormat(LOCALE);
const DATE = new Intl.DateTimeFormat(LOCALE, {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  timeZone: TIME_ZONE,
});
const DATE_TIME = new Intl.DateTimeFormat(LOCALE, {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
  timeZone: TIME_ZONE,
});

function parse(value: string | null | undefined): Date | null {
  if (!value) {
    return null;
  }
  // A bare date (YYYY-MM-DD) is a day in India, not midnight UTC.
  const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00+05:30` : value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function tidy(text: string): string {
  return text.replace('Sept', 'Sep');
}

export function number(value: number | null | undefined): string {
  return value === null || value === undefined ? NO_VALUE : NUMBER.format(value);
}

/** "05 Oct 2026". */
export function date(value: string | null | undefined): string {
  const parsed = parse(value);
  return parsed ? tidy(DATE.format(parsed)) : NO_VALUE;
}

/** "17 Oct 2026, 10:00 am", India time. */
export function dateTime(value: string | null | undefined): string {
  const parsed = parse(value);
  return parsed ? tidy(DATE_TIME.format(parsed)) : NO_VALUE;
}

/** "engineering_college" -> "Engineering college". */
export function readable(code: string | null | undefined): string {
  if (!code) {
    return NO_VALUE;
  }
  const words = code.replace(/_/g, ' ').trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
