# Plan Sheet UI Polish Plan

## Scope and intent
This plan defines a UI/UX polish pass for `templates/plan.html`, `static/plan.css`, and `static/plan.js` so the Plan page matches Chronicle's View page quality, dark theme, and scan speed.

## Critical issues in current UI (from `local/plan_v1.png`)
1. The page is visually detached from Chronicle branding (light background, default typography feel).
2. Table density is high but not readable: weak hierarchy, no zebra striping, and hard row tracking across many columns.
3. Week structure is unclear; Monday-to-Sunday blocks are not visually grouped.
4. Heatmap-style fills are oversaturated and dominate content instead of supporting it.
5. Controls and summary cards do not look like first-class Chronicle surfaces.

## Design goals
1. Match the View page visual system exactly: dark background, Space Grotesk typography, glassy dark cards, orange accent.
2. Preserve spreadsheet speed (fast entry, keyboard-first) while improving scanability.
3. Make weekly structure obvious at a glance with clear Monday-Sunday grouping.
4. Keep metric colors informative but restrained and accessible.

## Visual system updates
1. Apply Chronicle dark page background to Plan `body` (same layered gradient + subtle pattern used by View/Control/Setup).
2. Use consistent shell width, spacing, and card styling (`var(--dg-*)` tokens).
3. Upgrade headings and metadata hierarchy:
   - Strong page title and subtitle.
   - Compact metadata pill aligned to the right.
   - Summary cards with consistent label/value/detail typography.

## Table polish and structure
1. Add subtle alternating row backgrounds:
   - Even/odd stripe delta should be minimal (about 2-4% luminance difference).
2. Add week delineation (Monday-Sunday blocks):
   - `week-start` row: stronger top border + week badge.
   - `week-end` row: stronger bottom border.
   - Optional faint block tint per week to reinforce grouping.
3. Keep header sticky and improve readability:
   - Shorten labels where possible and show full labels via `title`.
   - Increase header contrast and vertical padding.
4. Improve numeric scan:
   - Right-align numeric metrics.
   - Keep editable cells left/center aligned for quick entry.

## Metric color strategy
1. Replace flat bright cell fills with restrained tinted backgrounds and text-safe contrast.
2. Keep a consistent severity scale:
   - `good`, `caution`, `hard`, `neutral` mapped to Chronicle-friendly tones.
3. Add a compact legend above the table so color meaning is explicit.

## Interaction polish
1. Keep current keyboard workflow; add stronger focus ring and active-row highlight.
2. Improve control bar styling (date picker, Today, Reload) to match Chronicle buttons.
3. Add sticky first columns for `Done`, `Date`, and `Distance` on wide screens.

## Implementation phases
1. Phase A (theme parity): body background, typography, cards, controls.
2. Phase B (table readability): zebra striping, spacing, numeric alignment, refined metric palette.
3. Phase C (week grouping): Monday/Sunday row classes, block delineation, week badge.
4. Phase D (QA): desktop/mobile pass, contrast check, keyboard-only workflow verification.

## Definition of done
1. Plan looks native to Chronicle dark theme with no light-page regressions.
2. Rows are easily trackable across the full table.
3. Monday-Sunday week boundaries are obvious without reading every date.
4. Metric colors communicate status without overpowering the UI.
5. Keyboard-first entry remains fast and unchanged in behavior.
