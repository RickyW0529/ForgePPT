# Prefect Agent Workflow Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed LangGraph pipeline with a dynamic Prefect 3 workflow engine that executes user-defined DAGs with parallel branches, merge nodes, and real-time SSE progress streaming.

**Architecture:** The Python worker receives a workflow definition JSON from the Gateway, validates the DAG, dynamically constructs a Prefect Flow at runtime using `task.submit()` to establish dependencies, and executes Agent nodes via LangChain tool-calling. Each node emits SSE events through a shared broadcaster. Merge nodes resolve page-level conflicts using `last_write_wins`.

**Tech Stack:** Python 3.12, Prefect 3.x, FastAPI, Pydantic v2, LangChain, pytest

---

## File Structure

| File | Responsibility |
|------|----------------|
| `python_worker/requirements.txt` | Add `prefect>=3.0` dependency |
| `python_worker/models/workflow_def.py` | Pydantic models: `WorkflowNode`, `WorkflowEdge`, `AgentNodeConfig`, `WorkflowDef` |
| `python_worker/workflow/dag.py` | DAG validation (`validate_dag`), topological sort, predecessor lookup |
| `python_worker/workflow/merge.py` | `merge_states()` with `last_write_wins` and `error_on_conflict` strategies |
| `python_worker/workflow/agent_registry.py` | Predefined agent roles, system prompts, tool bindings, `execute_agent(role, state, config)` |
| `python_worker/workflow/sse_broadcaster.py` | Shared SSE broadcaster module to avoid circular imports between executors and API routes |
| `python_worker/workflow/executors.py` | Prefect `@task` functions for each node type (`run_upload_node`, `run_agent_node`, `run_merge_node`, `run_export_node`, `run_page_allocator_node`) |
| `python_worker/workflow/orchestrator.py` | `execute_workflow(workflow_def, file_path)` — builds Prefect Flow dynamically and returns export path |
| `python_worker/api/routers/workflows.py` | FastAPI routes: `POST /workflows`, `GET /workflows/{id}`, `GET /workflows/{id}/events` (SSE) |
| `python_worker/api/main.py` | Register `workflows` router |
| `src/routes/workflows.rs` | Rust Gateway proxy routes for workflow endpoints |
| `src/routes/mod.rs` | Register Rust workflow routes |
| `python_worker/tests/test_dag.py` | Tests for cycle detection, topology sort, validation errors |
| `python_worker/tests/test_merge.py` | Tests for merge strategies and page conflict detection |
| `python_worker/tests/test_agent_registry.py` | Tests for agent role resolution and tool binding |
| `python_worker/tests/test_orchestrator.py` | Integration test: build workflow def → execute → assert export path |

---

## Execution Order

Execute tasks **in order**. Do not skip. Each task builds on the previous.

1. **Dependency & Model Foundation** — Install Prefect, define workflow Pydantic models
2. **DAG Utilities** — Validation, topology sort, predecessor lookup with tests
3. **Merge Logic** — State merging with conflict detection and tests
4. **Agent Registry** — Predefined roles, prompts, tool bindings with tests
5. **Prefect Executors & Orchestrator** — Task definitions and dynamic flow builder with integration test
6. **FastAPI Workflow Routes** — REST endpoints and SSE streaming
7. **Rust Gateway Proxy** — Wire Gateway to new Python worker endpoints

---

## Step Files

| Step | File | Focus |
|------|------|-------|
| `01-prefect-and-models.md` | `requirements.txt`, `models/workflow_def.py`, `tests/test_workflow_def.py` | Add Prefect dependency; define workflow definition Pydantic models |
| `02-dag-validation.md` | `workflow/dag.py`, `tests/test_dag.py` | DAG cycle detection, topological sort, validation rules |
| `03-merge-logic.md` | `workflow/merge.py`, `tests/test_merge.py` | PPTState merge with strategies and conflict detection |
| `04-agent-registry.md` | `workflow/agent_registry.py`, `tests/test_agent_registry.py` | Predefined agent roles and execution |
| `05-prefect-executors.md` | `workflow/executors.py`, `workflow/orchestrator.py`, `tests/test_orchestrator.py` | Prefect tasks and dynamic flow builder |
| `06-fastapi-routes.md` | `api/routers/workflows.py`, `api/main.py`, `tests/test_api.py` | REST + SSE endpoints |
| `07-rust-gateway-proxy.md` | `src/routes/workflows.rs`, `src/routes/mod.rs` | Gateway proxy routes |
