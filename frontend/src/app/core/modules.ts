import { Category, ModuleInfo } from './api/types';

/** The list with `key` and everything it needs (recursively), sorted. */
export function tick(selected: readonly string[], key: string, catalogue: readonly ModuleInfo[]): string[] {
  const chosen = new Set(selected);
  const todo = [key];
  while (todo.length) {
    const next = todo.pop()!;
    if (!chosen.has(next) || next === key) {
      chosen.add(next);
      todo.push(...(catalogue.find((module) => module.key === next)?.depends_on ?? []));
    }
  }
  return [...chosen].sort();
}

/** The list without `key` and without everything that needs it (recursively), sorted. */
export function untick(selected: readonly string[], key: string, catalogue: readonly ModuleInfo[]): string[] {
  const gone = new Set([key]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const module of catalogue) {
      if (!gone.has(module.key) && module.depends_on.some((need) => gone.has(need))) {
        gone.add(module.key);
        grew = true;
      }
    }
  }
  return selected.filter((item) => !gone.has(item)).sort();
}

export function defaultsFor(category: Category, catalogue: readonly ModuleInfo[]): string[] {
  return catalogue
    .filter((module) => module.default_for.includes(category))
    .map((module) => module.key)
    .sort();
}
