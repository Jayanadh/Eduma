/**
 * A suggested web address (subdomain) from an institution's name: lowercase ASCII letters, digits and single dashes,
 * at most 40 characters. Letters a web address cannot hold (Devanagari, Telugu…) are dropped; '' when too little is
 * left, so the admin types one. The server has the final say (reserved words, uniqueness).
 */
export function slugify(name: string): string {
  const full = name
    .toLowerCase()
    .replace(/['’]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  let slug = full.slice(0, 40);
  // Too long: end at the last whole word rather than part-way through one.
  if (full.length > 40 && full[40] !== '-' && slug.includes('-')) {
    slug = slug.slice(0, slug.lastIndexOf('-'));
  }
  slug = slug.replace(/-+$/, '');
  return slug.length >= 3 ? slug : '';
}
