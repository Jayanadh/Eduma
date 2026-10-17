import { LifecycleStatus } from '../../core/api/types';
import { PromptRequest } from '../../ui/confirm-dialog';

export type Move = { to: LifecycleStatus; label: string; tone: 'primary' | 'danger'; effect: string };

const ACTIVATE: Move = {
  to: 'active',
  label: 'Activate',
  tone: 'primary',
  effect: 'Its full public page goes live and its members can work as usual.',
};
const ARCHIVE: Move = {
  to: 'archived',
  label: 'Archive',
  tone: 'danger',
  effect: 'Its page and sign-in close for good. Its records are kept.',
};

/** The lifecycle actions open to an institution in each state (the server enforces the same table). */
export function allowedMoves(status: LifecycleStatus): Move[] {
  switch (status) {
    case 'setup':
      return [ACTIVATE, ARCHIVE];
    case 'active':
      return [
        {
          to: 'suspended',
          label: 'Suspend',
          tone: 'danger',
          effect: 'Its members are signed out and cannot sign in, and its page says it is unavailable. Nothing is deleted.',
        },
        ARCHIVE,
      ];
    case 'suspended':
      return [{ ...ACTIVATE, label: 'Reactivate', effect: 'Its page and sign-in open again.' }, ARCHIVE];
    default:
      return [];
  }
}

/** The question asked before a move: always a reason (kept in the audit log), and why, if not ready to activate. */
export function lifecycleQuestion(move: Move, name: string, missing: string[]): PromptRequest {
  const early = move.label === 'Activate' && missing.length > 0;
  return {
    title: `${move.label} ${name}?`,
    message: early ? `Not done yet: ${missing.join('; ')}. ${move.effect}` : move.effect,
    label: early ? 'Why activate it before it is ready?' : 'Reason',
    type: 'textarea',
    required: true,
    hint: 'Kept in the audit log.',
    confirmLabel: early ? 'Activate anyway' : move.label,
    tone: move.tone,
  };
}
