/**
 * The API answers every error with an RFC 9457 problem: {type, title, status, detail, code, errors[]}, where errors
 * lists field problems as {field: "admin.username", code, message}. These helpers turn that into words for people.
 */

const FALLBACK = 'Something went wrong. Please try again.';
const UNREACHABLE = 'Cannot reach the server. Check your connection.';
// The server answers 404 both for a record that does not exist and for one outside the person's reach.
const NOT_FOUND = 'Not found. It may have been removed, or it is not available to you.';

export type FieldProblem = { field: string; code: string; message: string };
export type Problem = {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  code?: string;
  errors?: FieldProblem[];
  current_version?: number | null;
};

/** The problem body of a failed HTTP call, or null if there is none (network failure, HTML error page). */
export function problemOf(err: unknown): Problem | null {
  if (err === null || typeof err !== 'object') {
    return null;
  }
  const body = (err as { error?: unknown }).error;
  return body !== null && typeof body === 'object' ? (body as Problem) : null;
}

export function isProblem(err: unknown, code: string): boolean {
  return problemOf(err)?.code === code;
}

function label(field: string): string {
  const words = field.replace(/\.\d+/g, '').replace(/[._]/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Turns anything thrown by an HTTP call into one sentence the user can read. */
export function apiErrorMessage(err: unknown): string {
  if (err === null || typeof err !== 'object') {
    return FALLBACK;
  }
  const { status } = err as { status?: unknown };
  if (status === 0) {
    return UNREACHABLE;
  }
  if (status === 404) {
    return NOT_FOUND;
  }
  const problem = problemOf(err);
  const first = problem?.errors?.[0];
  if (problem?.code === 'validation_failed' && first) {
    return first.field ? `${label(first.field)}: ${first.message}` : first.message;
  }
  return problem?.detail || FALLBACK;
}

/** Field path → first message, for showing errors next to the inputs they belong to. "" is the whole form. */
export function fieldErrors(err: unknown): Record<string, string> {
  const result: Record<string, string> = {};
  for (const { field, message } of problemOf(err)?.errors ?? []) {
    result[field] ??= message;
  }
  return result;
}
