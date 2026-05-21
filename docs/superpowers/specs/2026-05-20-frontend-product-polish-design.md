# Frontend Product Polish Design

> **Goal:** Upgrade the frontend into a more professional, product-grade workspace with a cohesive visual system, clearer hierarchy, and consistent styling across the header, canvas, sidebar, palette, nodes, and feedback states.

**Architecture:** Keep the current interaction model and React Flow workflow intact. This change is a visual and layout refinement only: unify the app shell, introduce a calmer surface/background system, standardize spacing and elevations, and align all panels and nodes to one design language. The implementation should favor small, focused style updates in existing components rather than structural rewrites.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, React Flow v12, Zustand

---

## Context

The current frontend already has the right functional layout:
- top header bar
- left node palette
- central React Flow canvas
- right parameter sidebar
- node cards with status states

What feels unfinished is the visual system. The page uses a mostly white background, mixed border/shadow treatments, and different panel styles that make the UI read as a prototype rather than a polished product.

This design keeps the existing workflow and component boundaries, but gives the app a unified SaaS-style presentation.

## Design Principles

1. **Professional, not flashy**
   - Use restrained colors and softer contrast.
   - Keep the deep blue brand tone as an accent, not a full-surface color.

2. **One surface language**
   - Panels, cards, node bodies, and popovers should share the same border radius, border tone, and shadow depth.
   - Avoid mixing flat white blocks with heavy shadows and bright fills.

3. **Clear hierarchy**
   - Header > primary work area > secondary controls.
   - Titles should read stronger than labels; labels stronger than helper text.

4. **Calm status feedback**
   - Status colors should be visible but not loud.
   - Success/error/pending states should support scanning without dominating the UI.

5. **Preserve workflow density**
   - The canvas remains the center of the experience.
   - Do not add decorative chrome that reduces usable space.

## Visual Direction

### Global shell
- Change the app background from pure white to a soft neutral surface.
- Use a consistent page rhythm: outer padding, inner panel boundaries, and subtle separation between regions.
- Add a more product-like shell around the main workspace so the layout feels intentional instead of directly stacked.

### Header bar
- Keep the current top placement and execution controls.
- Rework the header into a more polished navigation strip:
  - stronger title hierarchy
  - subtle divider or bottom border
  - less blocky button styling
  - status chip aligned with the rest of the product tone
- The header should feel like the control center of the app, not a standalone colored bar.

### Canvas area
- Maintain React Flow as the core interaction surface.
- Soften the background grid and keep the minimap/controls visually secondary.
- Canvas chrome should blend with the app surface instead of looking like a separate utility panel.
- The canvas should feel like a premium workspace area with enough contrast to keep nodes readable.

### Sidebar and palette
- Convert both left and right panels into more refined cards:
  - consistent header strip
  - clearer section spacing
  - subtle border and background contrast
- Palette items should look like compact product controls rather than colorful badges.
- The sidebar should clearly communicate that it is a configuration panel, not a generic drawer.

### Nodes
- Update node cards to use a consistent card system:
  - same radius family
  - same border weight
  - same shadow depth
  - same selected-state treatment
- Keep node headers visually distinct by type, but use muted accent treatments.
- Status borders should remain readable, but they should not overpower the node content.
- Node content should be slightly more spacious and legible.

### Toasts and status chips
- Align toast and status visuals with the same neutral/product tone.
- Keep green/red/blue semantics, but use softer fills and borders.
- Chips should feel like part of the product system, not separate ad hoc styles.

## File Scope

The visual refresh should primarily touch these files:

- `frontend/src/index.css`
- `frontend/tailwind.config.js`
- `frontend/src/App.tsx`
- `frontend/src/components/HeaderBar.tsx`
- `frontend/src/components/FlowCanvas.tsx`
- `frontend/src/components/SidebarPanel.tsx`
- `frontend/src/components/NodePalette.tsx`
- `frontend/src/components/ToastContainer.tsx`
- `frontend/src/components/nodes/UploadNode.tsx`
- `frontend/src/components/nodes/AgentNode.tsx`
- `frontend/src/components/nodes/PageAllocatorNode.tsx`
- `frontend/src/components/nodes/MergeNode.tsx`
- `frontend/src/components/nodes/ExportNode.tsx`

No store logic, API behavior, or workflow execution logic should change as part of this work.

## Implementation Breakdown

### Task 1: Global shell and theme tokens
- Update the global page background and base typography in `index.css`.
- Refine Tailwind theme tokens if needed so the UI has a tighter neutral palette.
- Ensure the app shell reads as a unified workspace rather than disconnected blocks.

### Task 2: Header and workspace framing
- Restyle `HeaderBar` to feel like a polished product nav/control strip.
- Adjust `App.tsx` so the major regions align with the new surface system and spacing.
- Keep the existing layout structure and execution behavior unchanged.

### Task 3: Sidebar and palette polish
- Rework `SidebarPanel` and `NodePalette` into cleaner, more consistent panels.
- Improve section titles, dividers, item spacing, and empty-state text.
- Make drag affordance and configuration affordance clearer without adding new interactions.

### Task 4: Canvas presentation
- Tone down React Flow chrome so the canvas feels integrated into the app shell.
- Adjust minimap, background, and controls to match the new design language.
- Keep node placement, drag/drop, and connections unchanged.

### Task 5: Node card refresh
- Restyle all node components to use one shared card language.
- Preserve per-node color accents, but make them more subtle and consistent.
- Keep status, selection, and handle affordances readable.

### Task 6: Toast and state feedback alignment
- Update toast styling to match the new surface system.
- Make success/error/info messages feel consistent with the rest of the product.
- Keep message semantics and behavior unchanged.

## Acceptance Criteria

- The frontend feels like a cohesive product workspace rather than a prototype.
- Header, canvas, palette, sidebar, and nodes all share the same visual system.
- The deep blue brand remains present but not overpowering.
- No workflow behavior changes, no store changes, and no API contract changes.
- The UI still supports the current upload, node edit, drag/drop, and execution flow.

## Verification Plan

- Run the frontend type check.
- Run the frontend build.
- Manually inspect the main workspace for layout regressions.
- Confirm that node drag/drop, selection, sidebar editing, upload, and execution still work.

## Open Questions Resolved

- **Scope:** whole frontend, not just the canvas.
- **Style direction:** professional product feel, not experimental or high-contrast dark mode.
- **Interaction scope:** visual refresh only; no workflow logic changes.
