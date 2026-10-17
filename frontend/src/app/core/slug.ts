/**
 * A suggested web address (subdomain) from an institution's name: lowercase ASCII letters, digits and single dashes,
 * at most 40 characters. Letters a web address cannot hold (Devanagari, Telugu…) are dropped; '' when too little is
 * left, so the admin types one. The server has the final say (reserved words, uniqueness).
 */
export function slugify(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/['’]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
    .replace(/-+$/, '');
  return slug.length >= 3 ? slug : '';
}
