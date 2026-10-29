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

/** Module names for the institution's own pages, which cannot read the platform's catalogue (backend
 * institutions/modules.py; keep the two in step). */
export const MODULE_LABELS: Readonly<Record<string, string>> = {
  admissions: 'Admissions and enrollment',
  students: 'Students and guardians',
  academics: 'Academic structure and timetable',
  attendance: 'Attendance',
  exams: 'Assessment and results',
  report_cards: 'Grades, sections, report cards and promotion',
  course_registration: 'Course registration, credits and degree audit',
  outcomes: 'Lab batches, projects and outcome evidence',
  affiliations: 'Affiliated colleges and central examinations',
  fees: 'Fees',
  communication: 'Messages, calls and online classes',
  reports: 'Reports and exports',
  library: 'Library',
  transport: 'Transport',
  hostel: 'Hostel and mess',
  hr_payroll: 'HR and payroll',
  assets: 'Assets, purchasing and labs',
  services: 'Student services and cases',
  placements: 'Placements, internships and alumni',
  quality: 'Quality, accreditation and research',
};
