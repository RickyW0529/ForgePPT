# ForgePPT

> AI-powered presentation editing through a visual workflow canvas.

ForgePPT lets you upload a `.pptx` file, configure AI editing instructions on a visual workflow canvas, and receive a refined or enhanced presentation. It combines a polyglot microservices stack — React, Rust, and Python — to process text refinement and SVG generation via Large Language Models.

## What it does

- **Upload** a PowerPoint file and preview its structure on a visual canvas.
- **Configure** AI editing nodes: text refinement (rewrite tone, style, or language) and SVG placeholder generation.
- **Execute** a LangGraph workflow that processes each instruction with an LLM.
- **Stream** real-time node status updates over SSE to the canvas.
- **Export** the modified presentation, preserving original formatting.

## Architecture at a glance

ForgePPT is composed of four containerized services orchestrated with Docker Compose:

```
+-------------------+         +-------------------+
|    Frontend       |  HTTP   |     Gateway       |
|  React + Vite     |<------->|   Rust + Axum     |
|  Port 5173        |   SSE   |   Port 3000       |
+-------------------+         +--------+----------+
                                         |
                    +--------------------+--------------------+
                    |                                         |
            +-------v--------+                       +-------v--------+
            | Python Worker  |                       |    Qdrant      |
            | FastAPI +      |                       |  Vector DB     |
            | LangGraph      |                       |  Port 6333     |
            | Port 8000      |                       +----------------+
            +----------------+
```

- **Frontend** — Visual workflow canvas built with React Flow v12. Users upload files, edit node parameters, and monitor execution status in real time.
- **Gateway** — Unified API entry point written in Rust (Axum). Handles request routing, CORS, rate limiting, SSE broadcasting, and proxying to the AI worker.
- **Python Worker** — FastAPI service that orchestrates the LangGraph DAG for parsing PPTX, running LLM-based text refinement and SVG generation, and recomposing the final file.
- **Qdrant** — Vector database storing user preference embeddings for contextual prompt enhancement.

## Quick start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env and add your OpenAI API key

# 2. Start all services
make up

# 3. Open the application
# Frontend:  http://localhost:5173
# Gateway:   http://localhost:3000
```

For development without Docker, see the [architecture docs](docs/architecture/en/05-deployment.md).

## Documentation

Detailed architecture design, API specifications, data flow diagrams, and deployment guides are available in:

- [English](docs/architecture/en/)
- [中文](docs/architecture/zh/)

## Tech stack highlights

- **Frontend:** React 18, TypeScript, Tailwind CSS, React Flow v12, Zustand
- **Gateway:** Rust, Axum 0.7, Tokio, Tower HTTP
- **AI Worker:** Python 3.11, FastAPI, LangGraph, LangChain, OpenAI/Anthropic
- **Vector DB:** Qdrant
- **Infrastructure:** Docker Compose

## Testing

```bash
make test      # Python + Rust unit tests
make test-e2e  # End-to-end tests (requires docker compose up)
```

## License

[AGPL v3.0](LICENSE)
