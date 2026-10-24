# Eduma slice 9 — communication and teacher-led classes (BUILD-09)

**Date:** 24 October 2026 · **Status:** from the spec pack, fast mode. **Source:** 03 WF-COM §10; 08 §7
Conversation/Participant/Message/MessageReceipt, CallRequest, ClassSession/ClassParticipant; 05 API §4.6 (class join);
TST-017, TST-018; D-12 (providers) and D-13 (recording) open. There is no real push, call or media provider: calls and
classes run their full state machines, and media access comes only from a configured **test-mode sandbox** that issues
signed, short-lived, role-bound tokens (no audio or video). Unconfigured → 409 `integration_not_configured`. Recording
is off and cannot be turned on. File attachments wait for malware scanning (not built).

## Decisions

| ID | Decision |
|---|---|
| S9-01 | **Communication policy** per institution (`communication.manage`): guardians may start conversations (default yes), calls enabled, classes enabled, default quiet hours. |
| S9-02 | **Conversations**: `staff` (any staff with any staff) and `family` (about one student: their assigned teachers or staff with `communication.manage`, and guardians whose active link allows messages). Participants keep their join/leave history; a newcomer sees history from when they joined. |
| S9-03 | **Messages** are saved before anything is delivered, numbered per conversation, idempotent per sender and client message id; read is a separate per-participant marker, never inferred from delivery. |
| S9-04 | **Access is rechecked on every read and write**: when a guardian link stops allowing messages or a teacher stops teaching the student, that participant loses the thread (404) and is marked left. Students do not use messaging or calls in this slice. Unrelated parents can't reach a teacher. |
| S9-05 | **Notifications** are in-app; each recipient's quiet hours delay them (they appear when quiet hours end). |
| S9-06 | **Calls** between a family thread's teacher and guardian, or between staff: requested → ringing (expires after 45 s → missed) → accepted / declined / canceled → ended; a callee in quiet hours is unavailable (409); accepting needs the media provider (else 409 `integration_not_configured`, state failed); an ended or answered call can't be answered again (stale push). |
| S9-07 | **Teacher-led classes** for a section or offering, hosted by its assigned teacher, only when classes are enabled: scheduled → live (host joined) → paused (no host) → live (host back) or ended (after 60 s grace, or by the host). Students on the roster join to a waiting room; the host admits or removes them; nobody joins a paused or ended class; students can't start one. |
| S9-08 | **Media tokens** (sandbox): signed with the institution's media secret, carry session, user, role and a revocation version, expire in 5 minutes; removing a participant bumps the version so reused tokens fail verification. Hosts get host tokens, students attendee tokens — never host. |
| S9-09 | **Attendance evidence**: join/leave times per participant; total time never double-counts a reconnect; not proof of engagement (the register stays the teacher's). |
| S9-10 | App and module `communication` (needs students) available; permission `communication.manage` (Institution Admin, Principal). |

## Tests

TST-017 (assigned teacher ↔ linked guardian with messages access can message and call; unrelated parent blocked;
student-initiated call blocked; quiet hours), TST-018 (revoked participant's token fails; final host leaves → paused,
student join refused; host back within grace → live; after grace → ended; recording off), idempotent messages,
history window, link revoked → thread gone, notification delay, unconfigured provider honest, isolation, module gate;
fees on the family portal follow `access_fees`.
