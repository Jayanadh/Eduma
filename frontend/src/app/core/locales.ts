/** Choices for an institution's country, time zone and currency, from the browser's own Intl data. */
export type Choice = { code: string; label: string };

const LETTERS = [...'ABCDEFGHIJKLMNOPQRSTUVWXYZ'];
/** Two-letter codes Intl can name that are not countries: groupings, retired countries and pseudo-locales. */
const NOT_COUNTRIES = new Set(
  'AC AN BU CP CQ CS DD DG DY EA EU EZ FX HV IC NH QO RH SU TA TP UK UN VD XA XB YD YU ZR ZZ'.split(' '),
);
/** ICU still lists some zones by their old names; the backend knows both, people know the new one. */
const RENAMED_ZONES: Readonly<Record<string, string>> = {
  'Africa/Asmera': 'Africa/Asmara',
  'America/Buenos_Aires': 'America/Argentina/Buenos_Aires',
  'America/Godthab': 'America/Nuuk',
  'America/Indianapolis': 'America/Indiana/Indianapolis',
  'Asia/Calcutta': 'Asia/Kolkata',
  'Asia/Katmandu': 'Asia/Kathmandu',
  'Asia/Rangoon': 'Asia/Yangon',
  'Asia/Saigon': 'Asia/Ho_Chi_Minh',
  'Atlantic/Faeroe': 'Atlantic/Faroe',
  'Europe/Kiev': 'Europe/Kyiv',
};

const byLabel = (a: Choice, b: Choice) => a.label.localeCompare(b.label);

const regions = new Intl.DisplayNames(['en'], { type: 'region', fallback: 'none' });
export const COUNTRIES: readonly Choice[] = LETTERS.flatMap((a) => LETTERS.map((b) => a + b))
  .filter((code) => !NOT_COUNTRIES.has(code))
  .map((code) => ({ code, label: regions.of(code) ?? '' }))
  .filter((choice) => choice.label)
  .sort(byLabel);

const currencies = new Intl.DisplayNames(['en'], { type: 'currency', fallback: 'code' });
export const CURRENCIES: readonly Choice[] = Intl.supportedValuesOf('currency')
  .map((code) => ({ code, label: `${code} · ${currencies.of(code)}` }));

export const TIME_ZONES: readonly Choice[] = Intl.supportedValuesOf('timeZone')
  .map((zone) => RENAMED_ZONES[zone] ?? zone)
  .map((code) => ({ code, label: code.replaceAll('_', ' ') }))
  .sort(byLabel);

/** The list, with `current` added if it is not in it (a value saved before, or a zone this browser names differently). */
export function withCurrent(choices: readonly Choice[], current: string): readonly Choice[] {
  return !current || choices.some((choice) => choice.code === current)
    ? choices
    : [{ code: current, label: current }, ...choices];
}
