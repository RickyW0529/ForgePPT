# Frontend Agent Workflow Canvas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the fixed 3-node canvas into a user-composable Agent Workflow canvas with draggable node palette, configurable Agent/PageAllocator/Merge nodes, free-form edges, and workflow execution via the new Prefect backend API.

**Architecture:** React Flow v12 powers the canvas. A Zustand `useWorkflowStore` manages the node/edge graph state, node configurations, and execution status. `ParamPanel` is rewritten to render configuration UIs per node type. Execution serializes the graph to the backend's `WorkflowDef` JSON, opens an SSE stream, and updates node borders based on real-time events.

**Tech Stack:** React 18, TypeScript, Vite, React Flow v12, Zustand, Tailwind CSS

---

## File Structure

| File | Responsibility |
|------|----------------|
| `frontend/src/types/workflow.ts` | TypeScript types: `WorkflowNode`, `WorkflowEdge`, `AgentNodeConfig`, `WorkflowDef`, `NodeType` |
| `frontend/src/stores/useWorkflowStore.ts` | Zustand store: nodes, edges, selected node, node configs, execution status, CRUD operations |
| `frontend/src/components/nodes/AgentNode.tsx` | React Flow custom node for `agent` type with role icon and status border |
| `frontend/src/components/nodes/PageAllocatorNode.tsx` | React Flow custom node for `page_allocator` type |
| `frontend/src/components/nodes/MergeNode.tsx` | React Flow custom node for `merge` type |
| `frontend/src/components/nodes/UploadNode.tsx` | Refactored from `UploadParserNode.tsx` |
| `frontend/src/components/nodes/ExportNode.tsx` | Refactored from `ExporterNode.tsx` |
| `frontend/src/components/nodes/index.ts` | Export all node type components |
| `frontend/src/components/NodePalette.tsx` | Sidebar palette with draggable Agent role cards and special nodes |
| `frontend/src/components/ParamPanel.tsx` | Rewrite: per-node-type config panel (agent, page_allocator, merge, upload, export) |
| `frontend/src/components/FlowCanvas.tsx` | Enable node drag-from-palette, edge creation/deletion, fitView |
| `frontend/src/components/HeaderBar.tsx` | Add "Execute" button that POSTs workflow definition |
| `frontend/src/hooks/useWorkflowSSE.ts` | SSE hook connecting to `/api/v1/workflows/{id}/events` and updating store |

---

## Execution Order

Execute tasks **in order**.

1. **Type Foundation & Store** — Workflow types and Zustand store
2. **Node Components** — New/custom node React components
3. **Canvas & Palette** — Draggable palette, editable canvas, edge behavior
4. **ParamPanel Rewrite** — Per-node configuration UI
5. **Execution & SSE** — HeaderBar execute button, workflow SSE hook, integration

---

## Step Files

| Step | File | Focus |
|------|------|-------|
| `01-types-and-store.md` | `types/workflow.ts`, `stores/useWorkflowStore.ts` | Workflow TypeScript types and graph state store |
| `02-node-components.md` | `components/nodes/*.tsx`, `components/nodes/index.ts` | Custom React Flow node components |
| `03-canvas-and-palette.md` | `components/FlowCanvas.tsx`, `components/NodePalette.tsx` | Draggable palette and editable canvas |
| `04-param-panel.md` | `components/ParamPanel.tsx` | Per-node-type configuration panel |
| `05-execution-and-sse.md` | `components/HeaderBar.tsx`, `hooks/useWorkflowSSE.ts`, `App.tsx` | Execute button, SSE streaming, integration |
