# 06 - Environment & Documentation

**Files:**
- Create: `README.md`
- Modify: `.gitignore`

---

- [ ] **Step 1: Write README**

```markdown
# PPT Agent

Node-Workflow based AI PPT editing tool.

## Quick Start

1. Copy environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

2. Start all services:
   ```bash
   make up
   ```

3. Access the application:
   - Frontend: http://localhost:5173
   - Gateway API: http://localhost:3000
   - Python Worker API: http://localhost:8000

## Testing

- Unit tests (Python): `cd python_worker && pytest tests/ -v`
- Unit tests (Rust): `cargo test`
- End-to-end: `make test-e2e`

## Project Structure

- `src/` — Rust Axum gateway
- `python_worker/` — Python FastAPI + LangGraph AI worker
- `frontend/` — React + React Flow canvas
- `scripts/` — Qdrant initialization
- `tests/e2e/` — End-to-end integration tests
```

- [ ] **Step 2: Update .gitignore**

```gitignore
# Rust
target/
Cargo.lock

# Python
__pycache__/
*.pyc
*.egg-info/
dist/
*.egg

# Node
node_modules/
dist/

# Environment
.env

# IDE
.idea/
.vscode/

# Uploads / temp
*.pptx
!tests/fixtures/*.pptx
```

- [ ] **Step 3: Commit**

```bash
git add README.md .gitignore
git commit -m "docs: add README and update .gitignore"
```
