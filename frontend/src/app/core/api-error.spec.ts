import { apiErrorMessage, fieldErrors, isProblem } from './api-error';

const problem = (status: number, error: object) => ({ status, error });

describe('apiErrorMessage', () => {
  it('reads problem detail', () =>
    expect(
      apiErrorMessage(
        problem(409, {
          code: 'version_conflict',
          detail: 'Reload the latest record and review your changes.',
        }),
      ),
    ).toBe('Reload the latest record and review your changes.'));

  it('labels the first field error', () =>
    expect(
      apiErrorMessage(
        problem(422, {
          code: 'validation_failed',
          detail: 'Taken.',
          errors: [{ field: 'admin.username', code: 'invalid', message: 'Taken.' }],
        }),
      ),
    ).toBe('Admin username: Taken.'));

  it('says unreachable on status 0', () =>
    expect(apiErrorMessage({ status: 0 })).toContain('Cannot reach the server'));

  it('explains 404 without saying whose record it was', () =>
    expect(apiErrorMessage(problem(404, { code: 'not_found', detail: 'Not found.' }))).toContain(
      'Not found',
    ));

  it('falls back for HTML error pages', () =>
    expect(apiErrorMessage(problem(502, '<html>bad gateway</html>' as unknown as object))).toBe(
      'Something went wrong. Please try again.',
    ));
});

describe('fieldErrors', () => {
  it('maps field errors by path', () =>
    expect(
      fieldErrors(
        problem(422, {
          code: 'validation_failed',
          errors: [
            { field: 'admin.username', code: 'invalid', message: 'Taken.' },
            { field: 'admin.username', code: 'invalid', message: 'Second message ignored.' },
            { field: '', code: 'invalid', message: 'Whole form.' },
          ],
        }),
      ),
    ).toEqual({ 'admin.username': 'Taken.', '': 'Whole form.' }));

  it('is empty for anything else', () => expect(fieldErrors({ status: 0 })).toEqual({}));
});

describe('isProblem', () => {
  it('matches the machine code', () => {
    expect(isProblem(problem(409, { code: 'version_conflict' }), 'version_conflict')).toBe(true);
    expect(isProblem(problem(409, { code: 'invalid_transition' }), 'version_conflict')).toBe(false);
    expect(isProblem(null, 'version_conflict')).toBe(false);
  });
});
