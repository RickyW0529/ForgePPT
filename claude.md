# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ForgePPT** (also referred to as "PPT Agent") is a Node-Workflow based AI PPT editing tool. It allows users to upload a `.pptx` file, apply AI-driven text refinement and SVG generation through a visual workflow canvas, and export the modified presentation.

## Architecture

The system is a polyglot microservices architecture orchestrated by Docker Compose:

- **`gateway` (Rust Axum, port 3000):** Unified HTTP/REST entry point. Handles CORS, rate limiting (token-bucket per IP), SSE streaming to the frontend, and proxies task execution to the Python worker. Serves as the API gateway for the React SPA.
- **`python-worker` (Python FastAPI + LangGraph, port 8000):** AI worker that runs the LangGraph DAG for the PPT editing pipeline. Contains three workflow nodes: `upload_parser`, `editor` (text refinement + SVG placeholder generation), and `exporter`. Also hosts the PPTX parse/recompose engine (`python-pptx`) and the Qdrant memory client.
- **`qdrant` (vector DB, ports 6333/6334):** Stores user preference embeddings (768-dim, Cosine, OpenAI `text-embedding-3-small`). The `user_preferences` collection is initialized via `scripts/init_qdrant.py`.
- **`frontend` (React 18 + Vite, port 5173):** React Flow v12 canvas with three fixed nodes (upload-parser → editor → exporter). Zustand stores handle file, task, SSE, and UI state. Tailwind CSS with a Deep Blue theme.

**Data Flow:** Frontend → Gateway → Python Worker. SSE events flow Gateway → Frontend for real-time node status updates.

**Key Data Model:** `PPTState` (Pydantic v2) is the canonical representation of a `.pptx` file — slides, text boxes, images, positions, sizes, and text styles. It is serialized to JSON for cross-language communication between Rust and Python.

## Directory Structure

```
src/                    # Rust Axum gateway
python_worker/          # Python FastAPI + LangGraph worker
  models/               # Pydantic data models (PPTState, workflow)
  services/             # Parser, Recomposer, Memory client
  llm/                  # LLM client abstraction, prompt templates
  workflow/             # LangGraph DAG and node implementations
  api/                  # FastAPI routes
  tests/                # pytest suite
frontend/               # React + Vite + React Flow (to be created)
scripts/                # Qdrant initialization
  init_qdrant.py
docs/superpowers/plans/ # Implementation plans (source of truth for feature work)
tests/e2e/              # End-to-end integration tests (Python + requests)
```

## Development Commands

### Rust (Gateway)

```bash
# Build
cargo build
cargo build --release

# Test (all)
cargo test

# Test (specific integration test)
cargo test --test integration_test
cargo test --test memory_integration

# Run gateway locally
cargo run
```

### Python (Worker)

```bash
cd python_worker

# Install dependencies
pip install -r requirements.txt

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_config.py -v

# Run FastAPI dev server
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Dev server
npm run dev          # port 5173

# Build
npm run build

# Run tests
npm run test         # vitest
```

### Docker Compose (Full Stack)

```bash
# Start all services
docker compose up -d --build

# Stop
docker compose down

# View logs
docker compose logs -f

# Run E2E tests (requires services up)
cd python_worker && pytest ../tests/e2e/ -v -m e2e
```

### Makefile (when present)

```bash
make up          # docker compose up -d --build
make down        # docker compose down
make test        # Python + Rust unit tests
make test-e2e    # E2E tests
make logs        # docker compose logs -f
```

## Environment Variables

Copy `.env.example` to `.env` and fill in secrets. Key variables:

- `PPT_OPENAI_API_KEY` — Required for LLM calls and embeddings
- `PPT_ANTHROPIC_API_KEY` — Optional, for Claude models
- `PPT_LLM_PROVIDER` — `openai` (default) or `anthropic`
- `PPT_LLM_MODEL` — e.g. `gpt-4o-mini`
- `BIND_ADDR` — Gateway listen address (default `0.0.0.0:3000`)
- `PYTHON_WORKER_URL` — Gateway-to-worker URL
- `QDRANT_URL` — Qdrant connection URL

## Plans as Source of Truth

Implementation work is driven by plans in `docs/superpowers/plans/`. When executing a plan, follow the steps exactly and verify at each checkpoint. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` skills for plan execution.

### Plan File Structure

Every plan follows a strict two-level structure: one top-level overview file plus a folder of numbered step files.

```
docs/superpowers/plans/
├── YYYY-MM-DD-plan-name.md          # Top-level overview: goal, architecture, execution order
└── plan-name/                       # Folder (kebab-case, matches overview filename without date prefix)
    ├── 01-step-name.md              # Individual numbered step files (NN-descriptive-name.md)
    ├── 02-step-name.md
    └── ...
```

- **Top-level file (`YYYY-MM-DD-plan-name.md`)**: Contains the plan overview — goal, architecture, tech stack, file structure, task summaries, and an `Execution Order` banner. It does NOT contain granular step-by-step implementation code.
- **Step folder (`plan-name/`)**: Contains the granular, executable step files. Each step file is a self-contained unit of work with failing tests, implementation code, verification commands, and commit instructions.
- **Step file naming**: Use two-digit prefix (`01-`, `02-`, ...) plus kebab-case description. This ensures correct sort order and clear progression.

When creating a new plan, always generate both the top-level overview and the step folder. Do not inline granular steps into the top-level file.

### Plan Execution Order

Plans have cross-service dependencies. Execute them in this order:

| # | Plan | Overview File | Step Folder | Depends On |
|---|------|--------------|-------------|------------|
| 1 | **Data Models & PPT Parse/Recompose** | `2026-05-13-data-models-and-ppt-parse.md` | `data-models-and-ppt-parse/` | None (foundation layer) |
| 2 | **AI Workflow Engine** | `2026-05-13-ai-workflow-engine.md` | `ai-workflow-engine/` | Data Models (uses PPTState) |
| 3 | **Memory Layer (Qdrant)** | `2026-05-13-memory-layer.md` | `memory-layer/` | AI Workflow Engine (uses LLMConfig); Rust endpoints need Gateway skeleton |
| 4 | **Rust Axum Gateway** | `2026-05-13-rust-gateway.md` | `rust-gateway/` | AI Workflow Engine (proxies Python API), Memory Layer (preference endpoints) |
| 5 | **Frontend Canvas** | `2026-05-13-frontend-canvas.md` | `frontend-canvas/` | Rust Gateway (REST API + SSE must exist) |
| 6 | **Deployment & Integration** | `2026-05-13-deployment-integration.md` | `deployment-integration/` | All previous plans (execute last) |

When starting implementation, always check the `Execution Order` banner in the top-level overview file to confirm prerequisites are satisfied.

## Behavioral Guidelines

These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

- Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes

- Touch only what you must. Don't "improve" adjacent code.
- Match existing style, even if you'd do it differently.
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

### 4. Goal-Driven Execution

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```
