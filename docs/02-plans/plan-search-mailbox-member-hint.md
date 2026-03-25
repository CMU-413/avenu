# Open Questions
None.

# Task Checklist
## Phase 1
- ☑ Add explicit search-match metadata to admin mailbox results so company mailboxes can distinguish direct name matches from member-name matches.
- ☑ Render member-match hint text under company results only when the active query matched a member rather than the company name itself.

## Phase 2
- ☑ Keep search grouping and navigation behavior unchanged while refining result presentation.
- ☑ Verify the new hint stays query-specific and does not appear for non-matching members or direct company matches.

## Phase 1: Query-Specific Match Metadata + Rendering
Affected files and changes
- `frontend/src/pages/admin/SearchMailbox.tsx`: enrich filtered mailbox results with query-specific member-match data and render secondary hint text for company matches driven by member names.

## Phase 2: Preserve Existing Search Behavior
Affected files and changes
- `frontend/src/pages/admin/SearchMailbox.tsx`: keep existing section grouping, ordering, and mailbox navigation while using the new match metadata only for display.
