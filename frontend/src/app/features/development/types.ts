export type OpportunityT = {
  id: string;
  title: string;
  kind: 'job' | 'internship';
  employer: string;
  description: string;
  programs: string[];
  min_cgpa: string | null;
  closes_on: string;
};
export type ApplicationT = {
  id: string;
  opportunity: { id: string; title: string; employer: string; kind: string };
  state: string;
  created_at: string;
  student?: { number: string; name: string };
  eligibility?: { cgpa: string | null; program: string | null; checked_on: string };
};
export type InternshipT = {
  id: string;
  student: { number: string; name: string };
  opportunity: string;
  employer: string;
  supervisor: string | null;
  score: string | null;
  remarks: string;
  evaluated_at: string | null;
};
export type MilestoneT = { id: string; title: string; due_on: string; needs_ethics: boolean; state: string; summary: string; note: string };
export type ScholarT = {
  id: string;
  student: { number: string; name: string };
  topic: string;
  started_on: string;
  supervisors: { id: string; name: string; role: string; current: boolean }[];
  ethics: { reference: string; committee: string; valid_from: string; valid_to: string; valid: boolean }[];
  milestones: MilestoneT[];
};
export type EvidenceT = {
  id: string;
  cycle: { id: string; framework: string; period: string };
  criterion: string;
  title: string;
  owner: string;
  state: 'requested' | 'submitted' | 'accepted' | 'returned';
  note: string;
  versions: { id: string; number: number; name: string; sha256: string; uploaded_at: string }[];
};
export type CycleT = { id: string; framework: string; period: string; frozen_at: string | null; snapshot_hash: string; requests?: EvidenceT[] };

export const ROW_STYLES = `
  .row,
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: end;
  }

  .grow {
    flex: 1 1 200px;
  }

`;
