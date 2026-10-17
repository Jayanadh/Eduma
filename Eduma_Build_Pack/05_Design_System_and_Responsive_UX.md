# Eduma — Design System and Responsive UX

**Version:** 0.1 · **Date:** 12 October 2026 · **Status:** Proposed visual and interaction specification.  
**Evidence boundary:** No logo, rendered wireframes, clickable prototype, screenshots or usability test results have been supplied or generated for this document. Token contrast below was calculated; the assembled UI has not been tested.  
**Related:** [Screen catalog](04_Navigation_and_Screen_Catalog.md), [screen review specification](06_Screen_Specs_and_Prototype_Review.md).

## 1. Visual direction and component approach

Proposed direction: a calm professional interface with neutral surfaces, a restrained indigo-blue accent, readable data, deliberate spacing and clear action hierarchy. Administrative workspaces favor comparison and review; teacher, student and parent workspaces favor the next task. Avoid decorative charts, large empty dashboard cards, excessive gradients and icon-only navigation where labels would help.

Use Angular Material and CDK as the proposed primary component foundation, with Eduma theme tokens and a small set of domain components. Angular documents Material as its reusable component library and CDK accessibility utilities for focus and announcements. This is a foundation, not a certification of the resulting application. Confirm compatible supported versions during implementation and evaluate complex grids before committing to any additional library. [Angular accessibility](https://angular.dev/best-practices/a11y), [Angular Material](https://material.angular.dev/), accessed 12 October 2026.

Prefer Material/CDK plus ordinary semantic HTML for forms, navigation, overlays and tables. Introduce a separate dependency only when a demonstrated requirement cannot be met maintainably; record size, licensing, accessibility and styling impact. Do not combine several competing design systems. Keep domain components such as student context, permission scope, academic period, fee allocation and publication review independent from third-party service SDKs.

## 2. Provisional tokens

These are draft values for discussion, not approved brand assets. CSS variables will use semantic names; components must not embed institution-specific colors.

| Token | Proposed value | Use |
|---|---|---|
| `surface.canvas` | `#F8FAFC` | Page background |
| `surface.default` | `#FFFFFF` | Forms, tables, dialogs |
| `surface.subtle` | `#F1F5F9` | Quiet grouping and table header |
| `text.primary` | `#0F172A` | Titles and body text |
| `text.secondary` | `#475569` | Supporting text, persistent labels |
| `text.muted` | `#64748B` | Less prominent text on white only |
| `border.subtle` | `#CBD5E1` | Decorative separators; not sole input boundary |
| `border.control` | `#64748B` | Essential input/interactive outline |
| `action.primary` | `#1D4ED8` | Primary button, links and selected controls |
| `action.primary.hover` | `#1E40AF` | Hover/pressed emphasis |
| `focus.ring` | `#1D4ED8` | Focus ring with contrasting offset |
| `success.text / background` | `#166534 / #F0FDF4` | Successful or active status |
| `warning.text / background` | `#92400E / #FFFBEB` | Pending attention |
| `danger.text / background` | `#B91C1C / #FEF2F2` | Error, failed validation |
| `info.text / background` | `#6D28D9 / #F5F3FF` | Informational state |

Calculated contrast ratios using relative sRGB luminance: primary text on white **17.85:1**; secondary **7.58:1**; muted **4.76:1**; white on primary action **6.70:1**; success pair **6.81:1**; warning **6.84:1**; danger **5.91:1**; info **6.48:1**. These calculations cover only the named pairs at full opacity. Muted text on another surface, overlays, disabled styles, focus against imagery and chart combinations need separate checks. Do not describe the entire theme as accessibility-tested.

Use a text label or icon plus label with every status. “Pending” and “Failed” must never rely on amber/red alone. A primary button is filled, a secondary button outlined or neutral, and a tertiary action a clearly identifiable text button. Use at most one visually dominant primary action in a local task area; destructive confirmation uses a specific action name such as “Suspend institution”.

## 3. Typography, spacing and density

Use a system sans-serif stack for the initial implementation; introduce a licensed, self-hosted brand font only if approved. Add tested script fallbacks for selected Indian languages. Launch language coverage remains open; text must be externalizable and the layout must tolerate expansion. Names remain Unicode, without forced capitalization or assumptions about surname structure.

| Element | Size / line height | Weight |
|---|---|---|
| Page title | 28 / 36 px; 24 / 32 on phone | 600 |
| Section title | 20 / 28 px | 600 |
| Card or dialog heading | 18 / 26 px | 600 |
| Body and form value | 16 / 24 px | 400 |
| Table body and supporting text | 14 / 20 px | 400 |
| Control label | 14 / 20 px | 500 |
| Dense metadata only | 12 / 18 px | 400 |

Use rem equivalents in implementation and support browser text resizing. Do not make essential instructions tiny metadata. Numeric amounts use tabular numerals and right alignment; identifiers remain selectable text. Meaningful labels wrap instead of being cut off. Provide a full-name detail where compact columns legitimately truncate.

Spacing scale: **4, 8, 12, 16, 24, 32, 48, 64 px**. Standard control height **44 px**, phone actions **48 px** where practical, row height **48–56 px** according to content. Dense mode may reduce administrative table spacing but not hide labels, keyboard focus or touch alternatives. Page padding: 16 px phone, 24 px tablet, 32 px desktop. Typical form width: 720 px; reading width about 70 characters; data workspaces may use available width up to 1600 px with sensible margins.

Corners: 8 px controls, 12 px panels, 16 px dialogs. Use subtle shadow for overlays and separation only; tables and forms rely on spacing and borders. Proposed motion durations are 120–180 ms for ordinary transitions; honor reduced-motion preferences and preserve all meaning without animation.

## 4. Responsive layout contract

Breakpoints describe content behavior and are draft implementation guidance: **compact <600 CSS px**, **medium 600–1023**, **wide ≥1024**; enhance spacious layouts above 1440. Review at 360, 390, 768, 1024 and 1440, plus 320 CSS-pixel reflow where applicable. Zoom, long translations, browser chrome and on-screen keyboards matter more than a device brand list.

| Component | Wide | Compact |
|---|---|---|
| Application shell | 240 px navigation + header + content | Drawer; visible institution label; stable page heading |
| Role navigation | Grouped sidebar | Parent/student may use 4–5 main destinations plus More; admins use drawer |
| Record form | Related fields in two columns | One column in meaningful reading order |
| Table | Comparable columns and controlled selection | Key fields plus detail view; true grids may scroll inside named region |
| Filters | Search and common filters visible | Search visible, filter sheet and applied chips |
| Detail page | Main column with side information | Ordered sections with status and primary action first |
| Timetable | Week grid and agenda alternatives | Day/agenda view, date navigation and session details |
| Marks grid | Spreadsheet-like entry with keyboard support | Student-by-student editor and review summary |
| Messages | Conversation list and selected thread | List or thread, visible back action, keyboard-safe composer |
| Live class | Main media with roster/control panels | Reachable media controls; panels as tabs/sheets |
| Approval | Side-by-side proposed/current values | Stacked labeled comparison and explicit decision area |

No global horizontal scroll for ordinary forms. A timetable or dense academic comparison may need two-dimensional scrolling; label the scroll region, retain understandable headers, and supply an agenda or individual-record alternative. Sticky actions must not cover the last form control, error message, caption or keyboard focus. The page must work in portrait and landscape without orientation locking.

## 5. Component interaction rules

**Forms:** persistent label, optional helper text, explicit required status, inline validation after meaningful interaction and error summary on submission. Preserve correct values after a recoverable failure. Use input modes appropriate to amount, email and telephone; a phone number is not a numeric quantity. Date-only fields remain date-only. Show the institution timezone on scheduled activities and preview the participant's local time when different.

**Tables:** named columns, visible sort direction, page-size control, scoped totals and server-backed filters. Selection clearly states “this page” versus a validated full result set. Bulk actions preview affected count, scope, exclusions and reversibility; partial failures produce downloadable authorized error details. Export is a separate permission and an auditable job, not a shortcut around masked columns.

**Dialogs:** reserve for bounded decisions. Long data collection uses a page. Opening a dialog moves focus into it; closing restores focus to the trigger or safe successor. Destructive actions show named resource, effect, reason and alternatives. A confirmation dialog cannot replace server state or permission checks.

**Uploads:** show allowed type and size before selection, per-file progress and processing state. Distinguish “uploaded” from “scan complete/accepted”. Provide retry and remove before submission. Institution branding requires image crop/preview but a meaningful text fallback always remains. A rejected file must not look available to other users.

**Dashboards:** every number has meaning, scope and freshness. Prefer actionable lists to decorative graphs. Graphs need a text/table alternative and intelligible axes; no invented growth percentages or synthetic data presented as live production metrics. Unknown and no data are separate from zero.

**Saving:** label draft, submitted, approved and published states distinctly. A local draft or pending request is not “Saved”. Server confirmation returns the new record version; stale-write conflicts show changed fields and safe reload/reapply choices. Never silently overwrite marks, attendance, permission assignments or finance data.

## 6. Common states and copy

| State | Required presentation and recovery |
|---|---|
| First use | Explain the next authorized setup task; avoid dead-end empty cards |
| No matches | Keep filters visible and offer clear/reset |
| Loading | Stable skeleton/indicator; mark affected region busy; avoid repeated announcements |
| Partial failure | Preserve usable data, identify unavailable portion, allow scoped retry |
| Validation error | Plain-language problem, field association and correction hint |
| Permission denied | Neutral explanation and legitimate contact path; no sensitive record detail |
| Read only/locked | Explain status, allowed view/export and correction process |
| Offline | Indicate connectivity; distinguish unsent drafts from committed records |
| Conflict | Show newer version exists; compare/reload without silent replacement |
| Session expired | Recover sign-in, then return to safe context if still authorized |
| Success | Specific result with next action; do not rely only on a disappearing toast |

Example copy: “Payment received; confirmation is pending” only when provider state supports that message. Otherwise use “Payment status is not yet confirmed. Check status before trying again.” Attendance uses “Draft saved” versus “Attendance submitted”. Configuration uses “Preview changes” then “Publish version”, not an ambiguous “Update all”.

Use human-readable dates such as **12 Oct 2026** for records; localized controls must resolve ambiguous dates. Start with INR and institution locale/timezone defaults, while retaining currency codes and international number formats in the data model. Amounts display their currency; avoid adding different currencies into one total.

## 7. Accessibility acceptance

Target WCAG 2.2 AA. Relevant requirements include normal-text contrast 4.5:1, large-text contrast 3:1, non-text control contrast, reflow, keyboard access, visible/unobscured focus, accessible names, error identification and live captions where applicable. The WCAG 2.2 AA minimum target-size criterion is 24 CSS px with exceptions; Eduma's proposed 44–48 px controls are a separate usability choice. [W3C quick reference](https://www.w3.org/WAI/WCAG22/quickref/), accessed 12 October 2026.

Test with keyboard only and representative screen readers, not automated checks alone. Verify skip navigation, logical headings, dialog focus, route-change focus, table headers, checkbox names and non-disruptive announcements. No interaction may require dragging alone; provide buttons or keyboard alternatives for timetable placement and file ordering. Do not block password managers or paste. Financial/result submissions have review/correction steps. Live media needs an explicit accessibility review including caption-provider capability; do not claim overall AA while an in-scope media requirement remains unaddressed.

## 8. Branding authority and review evidence

System Admin supplies initial images/details during onboarding. Institution Admin can replace authorized institutional branding and select validated theme accents. Preserve Eduma identity in shared/platform areas, institution identity in institution areas, and a clear active context. Theme editing previews real components and validates allowed contrast pairs; reject inaccessible combinations with a usable alternative. Institutions cannot change semantic error colors, authorization behavior or remove required status labels.

When the logo arrives, collect SVG or high-resolution transparent artwork, light/dark variants if available, minimum-space guidance and usage rights. Until then use the text “Eduma”, not a fabricated approved logo. A second dark theme is an open scope decision, not automatically included.

Review five examples together: platform directory, institution configuration, attendance, parent home and payment exception. Record screenshot/prototype link, viewport, data fixture, reviewer, issue, decision and date. The current status of each is **not yet rendered or reviewed**. This document supplies the criteria for that review and can be revised without generating the application.
