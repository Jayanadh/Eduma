/** Why a registration was refused, in words (slice 5c rule codes). */
export const RULES: Record<string, string> = {
  window_closed: 'Registration is not open',
  hold: 'A hold stops registration',
  offering_closed: 'Not open for registration',
  not_in_regulation: 'Not in the regulation',
  prerequisite: 'Prerequisite not passed yet',
  already_passed: 'Already passed',
  credit_limit: 'Over the credit limit',
  linked_section: 'Register a lecture with one of its labs',
  capacity_exhausted: 'No seats left',
  not_enrolled: 'Not enrolled',
  rejected: 'Rejected',
};
