/** What a change to a role's permissions adds and removes, each sorted. */
export function roleDiff(before: readonly string[], after: readonly string[]): { added: string[]; removed: string[] } {
  return {
    added: after.filter((name) => !before.includes(name)).sort(),
    removed: before.filter((name) => !after.includes(name)).sort(),
  };
}
