# Frontend Product Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the frontend into a more professional product workspace by unifying the shell, sidebar, canvas, node cards, and feedback states into one cohesive visual system.

**Architecture:** Keep the current React Flow interaction model, workflow store, and API behavior unchanged. This plan only refines the presentation layer: global theme tokens, app shell framing, panel styling, canvas chrome, node card treatment, and toast styling. Each task should make a visible UI improvement without altering workflow logic.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, React Flow v12, Zustand

---

## File Structure

| File | Responsibility |
|---|---|
| `frontend/src/index.css` | Global background, base typography, and app-level surface styling |
| `frontend/tailwind.config.js` | Theme tokens for neutral surfaces, borders, and brand accents |
| `frontend/src/App.tsx` | Outer shell framing and workspace layout spacing |
| `frontend/src/components/HeaderBar.tsx` | Header styling, title hierarchy, status chip, and execute button presentation |
| `frontend/src/components/FlowCanvas.tsx` | Canvas chrome, background, controls, and minimap presentation |
| `frontend/src/components/SidebarPanel.tsx` | Right-side configuration panel shell and empty state styling |
| `frontend/src/components/NodePalette.tsx` | Left palette shell, section header, and drag item styling |
| `frontend/src/components/ToastContainer.tsx` | Toast surface styling and feedback tone |
| `frontend/src/components/nodes/UploadNode.tsx` | Upload node card styling |
| `frontend/src/components/nodes/AgentNode.tsx` | Agent node card styling |
| `frontend/src/components/nodes/PageAllocatorNode.tsx` | Page allocator node card styling |
| `frontend/src/components/nodes/MergeNode.tsx` | Merge node card styling |
| `frontend/src/components/nodes/ExportNode.tsx` | Export node card styling |

## Execution Order

1. Global shell and theme tokens
2. Header and workspace framing
3. Sidebar and palette polish
4. Canvas presentation
5. Node card refresh
6. Toast and state feedback alignment

---

## Task 1: Global shell and theme tokens

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/tailwind.config.js`

- [ ] **Step 1: Inspect the current base styles and theme tokens**

Review `frontend/src/index.css` and `frontend/tailwind.config.js` to confirm the current base background, font, and color palette. The app currently uses a white page background and a `deepblue` brand scale; the goal is to keep the brand scale but make the overall neutral surface more refined.

- [ ] **Step 2: Update the global surface styling**

Replace the current base body styling with a softer workspace background and a better default font stack. Use this CSS shape as the target:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color-scheme: light;
}

html,
body,
#root {
  min-height: 100%;
}

body {
  margin: 0;
  padding: 0;
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f4f7fb;
  color: #0f172a;
}

* {
  box-sizing: border-box;
}
```

- [ ] **Step 3: Tighten the neutral theme tokens**

Refine the Tailwind palette to support more professional surfaces and separators while keeping the existing brand blues. Use this structure as the target:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        deepblue: {
          50: '#EDF3FA',
          100: '#D8E5F4',
          200: '#B8CEE7',
          300: '#86A9D2',
          400: '#5E87BA',
          500: '#3E688F',
          600: '#2D5275',
          700: '#23405B',
          800: '#182E44',
          900: '#0F1D2E',
        },
        surface: '#F4F7FB',
        panel: '#FFFFFF',
        border: '#D9E2EC',
        muted: '#64748B',
      },
      boxShadow: {
        soft: '0 10px 30px rgba(15, 23, 42, 0.06)',
        insetSoft: 'inset 0 1px 0 rgba(255, 255, 255, 0.65)',
      },
      borderRadius: {
        xl2: '1.25rem',
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 4: Verify the frontend still compiles**

Run:

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npx tsc --noEmit
```

Expected: no TypeScript errors.

- [ ] **Step 5: Commit the theme foundation**

```bash
git add frontend/src/index.css frontend/tailwind.config.js
git commit -m "feat: refine global theme foundation for product polish

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Task 2: Header and workspace framing

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/HeaderBar.tsx`

- [ ] **Step 1: Inspect the current app shell and header markup**

Review how the current app stacks the header, canvas, and sidebar so the shell can be restyled without changing layout behavior.

- [ ] **Step 2: Restyle the outer app frame**

Update `App.tsx` so the outer wrapper reads like a workspace shell rather than a bare full-screen stack. Use a light page background, padding around the main workspace, and rounded outer edges where appropriate while keeping the same child ordering.

- [ ] **Step 3: Restyle the header into a polished control strip**

Update `HeaderBar.tsx` to use a subtler surface, clearer title hierarchy, and more restrained action button styling. Keep the same execution behavior and status logic, but make the header look like a product navigation/control bar.

A good target structure is:

```tsx
<header className="h-14 flex items-center justify-between px-5 border-b border-border bg-white/90 backdrop-blur-sm shadow-[0_1px_0_rgba(255,255,255,0.7)]">
  <div className="flex items-center gap-3">
    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-deepblue-700 text-white shadow-soft">...</div>
    <div>
      <div className="text-sm font-semibold text-slate-900">PPT Agent</div>
      <div className="text-xs text-muted">Workflow canvas for PPT editing</div>
    </div>
  </div>
  <div className="flex items-center gap-3">...</div>
</header>
```

Keep the execution button, status chip, and loading state behavior unchanged.

- [ ] **Step 4: Verify the frontend still compiles**

Run:

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npx tsc --noEmit
```

Expected: no TypeScript errors.

- [ ] **Step 5: Commit the shell refresh**

```bash
git add frontend/src/App.tsx frontend/src/components/HeaderBar.tsx
git commit -m "feat: polish the app shell and header for a professional layout

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Task 3: Sidebar and palette polish

**Files:**
- Modify: `frontend/src/components/SidebarPanel.tsx`
- Modify: `frontend/src/components/NodePalette.tsx`
- Modify: `frontend/src/components/ParamPanel.tsx`

- [ ] **Step 1: Inspect the panel and palette markup**

Review the existing sidebar and palette layout so both sides can share the same panel language without changing their behavior.

- [ ] **Step 2: Restyle the palette as a compact product panel**

Update `NodePalette.tsx` so the panel uses a clearer header, softer borders, and drag items that look like product controls instead of colored pills. Keep the same drag data and item order.

- [ ] **Step 3: Restyle the sidebar shell**

Update `SidebarPanel.tsx` so the collapsed and expanded states use the same panel styling language as the palette. Improve the empty-state text and section header spacing.

- [ ] **Step 4: Restyle the parameter panel surfaces**

Update `ParamPanel.tsx` so labels, inputs, buttons, and helper text feel aligned with the new product styling. Keep all current form behavior, state updates, and validation logic unchanged.

- [ ] **Step 5: Verify the frontend still compiles**

Run:

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npx tsc --noEmit
```

Expected: no TypeScript errors.

- [ ] **Step 6: Commit the panel polish**

```bash
git add frontend/src/components/SidebarPanel.tsx frontend/src/components/NodePalette.tsx frontend/src/components/ParamPanel.tsx
git commit -m "feat: polish the side panels and parameter surfaces

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Task 4: Canvas presentation

**Files:**
- Modify: `frontend/src/components/FlowCanvas.tsx`

- [ ] **Step 1: Inspect the current React Flow chrome**

Review the canvas wrapper, background, controls, and minimap so the visual adjustments stay confined to presentation.

- [ ] **Step 2: Tone down the canvas chrome**

Update `FlowCanvas.tsx` so the canvas reads as a premium workspace area. Soften the background grid, make the controls and minimap visually secondary, and wrap the canvas in a subtle panel surface.

A good target structure is:

```tsx
<div className="flex-1 h-full rounded-2xl border border-border bg-white shadow-soft overflow-hidden">
  <ReactFlow ...>
    <Background gap={24} size={1} className="bg-surface" />
    <Controls className="!bg-white !border !border-border !shadow-soft" />
    <MiniMap className="!bg-white/95 !border !border-border" />
  </ReactFlow>
</div>
```

Keep node placement, drag/drop, edge handling, and view fitting behavior unchanged.

- [ ] **Step 3: Verify the frontend still compiles**

Run:

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npx tsc --noEmit
```

Expected: no TypeScript errors.

- [ ] **Step 4: Commit the canvas polish**

```bash
git add frontend/src/components/FlowCanvas.tsx
git commit -m "feat: refine the React Flow canvas presentation

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Task 5: Node card refresh

**Files:**
- Modify: `frontend/src/components/nodes/UploadNode.tsx`
- Modify: `frontend/src/components/nodes/AgentNode.tsx`
- Modify: `frontend/src/components/nodes/PageAllocatorNode.tsx`
- Modify: `frontend/src/components/nodes/MergeNode.tsx`
- Modify: `frontend/src/components/nodes/ExportNode.tsx`

- [ ] **Step 1: Inspect the current node card variants**

Review the five node components and note the shared structure so the visual refresh can be applied consistently.

- [ ] **Step 2: Standardize the card shell**

Update all node components to share one card language: consistent radius, border, shadow, and selected-state treatment. Keep the status border behavior, but soften the colors and make each node header treatment more muted.

A shared visual target is:

```tsx
<div className={`overflow-hidden rounded-2xl border bg-white shadow-soft ${statusBorder[data.status]} ${selected ? 'ring-2 ring-deepblue-300' : 'ring-0'}`}>
```

Use muted header accents per node type, but avoid overly bright fills.

- [ ] **Step 3: Improve legibility inside node bodies**

Increase spacing slightly, keep labels readable, and make helper text quieter. Ensure the handles remain visible and the content does not feel cramped.

- [ ] **Step 4: Verify the frontend still compiles**

Run:

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npx tsc --noEmit
```

Expected: no TypeScript errors.

- [ ] **Step 5: Commit the node card refresh**

```bash
git add frontend/src/components/nodes/UploadNode.tsx frontend/src/components/nodes/AgentNode.tsx frontend/src/components/nodes/PageAllocatorNode.tsx frontend/src/components/nodes/MergeNode.tsx frontend/src/components/nodes/ExportNode.tsx
git commit -m "feat: unify node card styling across the workflow canvas

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Task 6: Toast and state feedback alignment

**Files:**
- Modify: `frontend/src/components/ToastContainer.tsx`

- [ ] **Step 1: Inspect the current toast styles**

Review the toast icon, color, and border treatment so the new surface language can be applied without changing behavior.

- [ ] **Step 2: Restyle toast surfaces**

Update `ToastContainer.tsx` so toast cards use the same border radius, border tone, and shadow family as the rest of the app. Keep the icon mapping and auto-dismiss behavior unchanged, but soften the fill colors and improve visual alignment.

A good target structure is:

```tsx
<div className={`flex items-start gap-3 rounded-2xl border bg-white px-4 py-3 shadow-soft ${styles[toast.type]}`}>
```

- [ ] **Step 3: Verify the frontend still compiles**

Run:

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npx tsc --noEmit
```

Expected: no TypeScript errors.

- [ ] **Step 4: Commit the feedback polish**

```bash
git add frontend/src/components/ToastContainer.tsx
git commit -m "feat: align toast feedback with the new product surface

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Final Verification

After all tasks are complete:

- Run `cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend && npm run build`
- Open the app and confirm the shell, palette, sidebar, canvas, nodes, and toasts feel visually consistent
- Confirm the upload, drag/drop, parameter editing, and execution flow still behave exactly as before

## Notes for Implementation

- Keep the changes visual-only.
- Do not modify Zustand store logic.
- Do not change API requests or response handling.
- Preserve React Flow behavior, node types, and workflow execution flow.
- Prefer small local style updates over structural refactors.
