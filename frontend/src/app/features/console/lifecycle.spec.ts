import { allowedMoves, lifecycleQuestion } from './lifecycle';

describe('allowedMoves', () => {
  it('follows the lifecycle', () => {
    expect(allowedMoves('setup').map((move) => move.to)).toEqual(['active', 'archived']);
    expect(allowedMoves('active').map((move) => move.to)).toEqual(['suspended', 'archived']);
    expect(allowedMoves('suspended').map((move) => move.to)).toEqual(['active', 'archived']);
    expect(allowedMoves('archived')).toEqual([]);
  });

  it('names each action', () => {
    expect(allowedMoves('setup')[0].label).toBe('Activate');
    expect(allowedMoves('suspended')[0].label).toBe('Reactivate');
    expect(allowedMoves('active')[0].label).toBe('Suspend');
  });
});

describe('lifecycleQuestion', () => {
  it('asks for a reason naming the action and the institution', () => {
    const [suspend] = allowedMoves('active');
    const question = lifecycleQuestion(suspend, 'Aster School', []);
    expect(question.title).toBe('Suspend Aster School?');
    expect(question.required).toBe(true);
    expect(question.type).toBe('textarea');
    expect(question.tone).toBe('danger');
    expect(question.message).toContain('signed out');
  });

  it('lists unmet readiness before activating anyway', () => {
    const [activate] = allowedMoves('setup');
    const question = lifecycleQuestion(activate, 'Vector Engineering College', ['Public page is published']);
    expect(question.message).toContain('Public page is published');
    expect(question.label).toBe('Why activate it before it is ready?');
    expect(question.confirmLabel).toBe('Activate anyway');
  });
});
