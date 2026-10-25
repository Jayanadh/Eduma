export type CaseNoteT = { text: string; visibility: 'requester_visible' | 'internal'; by: string; at: string };
export type CaseT = {
  id: string;
  number: string;
  case_type: 'service_request' | 'grievance' | 'counselling' | 'safeguarding';
  type_label: string;
  confidential: boolean;
  state: 'submitted' | 'assigned' | 'resolved' | 'appealed';
  state_label: string;
  created_at: string;
  seen_as: 'requester' | 'officer' | 'triage';
  subject?: string;
  description?: string;
  requester?: string;
  assignee?: string | null;
  due_at?: string;
  overdue?: boolean;
  notes?: CaseNoteT[];
  resolutions?: { stage: 'original' | 'appeal'; text: string; at: string }[];
  appeal?: { reason: string; at: string } | null;
  can_appeal?: boolean;
};

export const CASE_TYPES = [
  ['service_request', 'Service request (certificates, records, facilities)'],
  ['grievance', 'Academic grievance (confidential)'],
  ['counselling', 'Counselling (confidential)'],
  ['safeguarding', 'Safeguarding concern (confidential)'],
] as const;
