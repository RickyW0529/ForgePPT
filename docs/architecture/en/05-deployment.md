# Deployment Architecture

## 1. Deployment Topology

```
+=====================================================================+
|                     Docker Compose Deployment Topology              |
+=====================================================================+

  Host Machine
  +---------------------------------------------------------------+
  |                                                               |
  |  Port 5173   +--------------------+                           |
  |  <--------- |     frontend       |                           |
  |              |   (Node 20 Slim)   |                           |
  |              |   Vite Dev Server  |                           |
  |              +---------+----------+                           |
  |                        |                                      |
  |                        | HTTP/REST + SSE                     |
  |                        | (Vite proxy: /api/* -> gateway)      |
  |                        v                                      |
  |  Port 3000   +--------------------+                           |
  |  <--------- |     gateway        |                           |
  |              |   (Debian Slim)    |                           |
  |              |   Rust Axum Binary |                           |
  |              +---------+----------+                           |
  |                        |                                      |
  |                        | HTTP/REST (reqwest)                  |
  |                        |                                      |
  |              +---------+----------+  +--------------------+   |
  |              |   python-worker    |  |      qdrant        |   |
  |  Port 8000   |  (Python 3.11 Slim)|  |   (qdrant:v1.11.0) |   |
  |  <--------- |   FastAPI/Uvicorn  |  |   768-dim Cosine   |   |
  |              +--------------------+  +--------------------+   |
  |  Port 6333                                                   |
  |  <--------------------------------------------------------  |
  |                                                               |
  +---------------------------------------------------------------+

  Docker Network: forge_default (bridge)
  Volumes: qdrant_storage, pptx_uploads
```

### 1.1 Service Dependency Chain

```
+-------------------------------------------------------------------+
|                     Service Startup Dependency Chain              |
+-------------------------------------------------------------------+

  qdrant (starts first)
    |
    | healthcheck: curl http://localhost:6333/healthz
    | interval: 5s, retries: 5
    v
  python-worker
    |
    | entrypoint.sh:
    |   1. Wait for Qdrant (30s max)
    |   2. python3 /scripts/init_qdrant.py
    |   3. uvicorn api.main:app --host 0.0.0.0 --port 8000
    |
    | healthcheck: curl http://localhost:8000/health
    | interval: 5s, retries: 5
    v
  gateway
    |
    | healthcheck: curl http://localhost:3000/health
    | interval: 5s, retries: 5
    v
  frontend (starts last)
```

---

## 2. Docker Compose Configuration Details

### 2.1 Service Definitions

| Service | Image/Build | Port | Dependencies |
|------|-----------|------|------|
| **qdrant** | `qdrant/qdrant:v1.11.0` | 6333, 6334 | — |
| **python-worker** | `python:3.11-slim` (custom) | 8000 | qdrant (healthy) |
| **gateway** | `rust:1.80` → `debian:bookworm-slim` | 3000 | python-worker (healthy) |
| **frontend** | `node:20-slim` (custom) | 5173 | gateway |

### 2.2 Network Topology

```yaml
# Docker Compose implicitly creates a bridge network
networks:
  default:
    driver: bridge
    name: forge_default
```

**Inter-service DNS Resolution:**
| Source Service | Target Service | Internal Address |
|--------|----------|----------|
| frontend (Vite proxy) | gateway | `http://gateway:3000` |
| gateway | python-worker | `http://python-worker:8000` |
| gateway | qdrant | `http://qdrant:6333` |
| python-worker | qdrant | `http://qdrant:6333` |

### 2.3 Volumes

| Volume Name | Mount Point | Purpose | Persistent |
|------|--------|------|--------|
| `qdrant_storage` | `/qdrant/storage` | Qdrant vector data | Yes (named volume) |
| `pptx_uploads` | `/tmp/uploads` | PPTX upload staging | Yes (named volume) |
| `./frontend` | `/app` | Frontend source hot reload | No (bind mount) |
| `./python_worker` | `/app` | Python source hot reload | No (bind mount) |
| `/app/node_modules` | — | Exclude node_modules override | Anonymous volume |

---

## 3. Dockerfiles for Each Service

### 3.1 Gateway (Rust Multi-stage Build)

```dockerfile
# Build stage
FROM rust:1.80 AS builder

WORKDIR /app

# Cache dependencies
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release && rm -rf src

# Build application
COPY src ./src
COPY tests ./tests
RUN touch src/main.rs && cargo build --release

# Runtime stage
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/target/release/forge-ppt /app/forge-ppt

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

CMD ["./forge-ppt"]
```

**Build Strategy:**
1. **Dependency cache layer**: Copy `Cargo.toml`/`Cargo.lock` first, build a dummy main to cache dependency compilation
2. **Source compilation layer**: Copy `src/` and `tests/`, force recompilation (`touch src/main.rs`)
3. **Runtime minimization**: Based on `debian:bookworm-slim`, only install `ca-certificates` and `curl`
4. **Health check**: Check `/health` every 30s, with a 5s startup grace period

**Image Characteristics:**
- Multi-stage build; final image does not contain the Rust toolchain
- Statically compiled binary (depends on glibc, hence Debian rather than Alpine)
- Binary path: `/app/forge-ppt`

### 3.2 Python Worker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies (required by python-pptx, lxml, cairo, etc.)
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libcairo2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY python_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY python_worker/ .
COPY scripts/init_qdrant.py /scripts/init_qdrant.py

# Entrypoint
COPY python_worker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
```

**Entrypoint Script Logic:**

```bash
#!/bin/bash
set -e

# 1. Wait for Qdrant to be ready (up to 30 seconds)
for i in {1..30}; do
    if curl -sf http://qdrant:6333/healthz; then
        break
    fi
    sleep 1
done

# 2. Initialize Qdrant collection
python3 /scripts/init_qdrant.py || true

# 3. Start FastAPI server
exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Startup Sequence:**
1. Docker Compose waits for the `qdrant` health check to pass
2. The `python-worker` container starts and executes `entrypoint.sh`
3. `entrypoint.sh` polls Qdrant internally (30 attempts, 1s interval)
4. Runs `init_qdrant.py` to create/confirm the `user_preferences` collection
5. Starts `uvicorn` (`--reload` development mode)

### 3.3 Frontend

```dockerfile
FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

**Build Strategy:**
- Based on `node:20-slim`
- Runs in development mode: `npm run dev -- --host 0.0.0.0`
- Exposes 5173 for external access
- Source hot reload via bind mount `./frontend:/app`
- `node_modules` protected by an anonymous volume to prevent bind mount overwrite

### 3.4 Qdrant (Official Image)

```yaml
services:
  qdrant:
    image: qdrant/qdrant:v1.11.0
    ports:
      - "6333:6333"   # REST API
      - "6334:6334"   # gRPC API
    volumes:
      - qdrant_storage:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 5s
      timeout: 3s
      retries: 5
```

---

## 4. Environment Variable Mapping

### 4.1 Variable Propagation Chain

```
+-------------------------------------------------------------------+
|                  Environment Variable Propagation Chain            |
+-------------------------------------------------------------------+

  .env File (Host)
  =================
  PPT_OPENAI_API_KEY=sk-xxx
  PPT_LLM_MODEL=gpt-4o-mini
  MAX_UPLOAD_SIZE=52428800
  RATE_LIMIT_PER_MINUTE=60

       |
       | docker compose up
       v

  python-worker
  =============
  PPT_OPENAI_API_KEY=${PPT_OPENAI_API_KEY}      (pass-through)
  PPT_ANTHROPIC_API_KEY=${PPT_ANTHROPIC_API_KEY} (pass-through)
  PPT_LLM_PROVIDER=${PPT_LLM_PROVIDER:-openai}   (default value)
  PPT_LLM_MODEL=${PPT_LLM_MODEL:-gpt-4o-mini}    (default value)
  PPT_LLM_TEMPERATURE=${PPT_LLM_TEMPERATURE:-0.3}(default value)
  QDRANT_URL=http://qdrant:6333                   (hard-coded internal address)

  gateway
  =======
  BIND_ADDR=0.0.0.0:3000                          (hard-coded)
  PYTHON_WORKER_URL=http://python-worker:8000     (hard-coded internal address)
  QDRANT_URL=http://qdrant:6333                   (hard-coded internal address)
  PPT_OPENAI_API_KEY=${PPT_OPENAI_API_KEY}        (pass-through)
  MAX_UPLOAD_SIZE=${MAX_UPLOAD_SIZE:-52428800}    (default value)
  RATE_LIMIT_PER_MINUTE=${RATE_LIMIT_PER_MINUTE:-60} (default value)

  frontend
  ========
  VITE_API_BASE_URL=http://localhost:3000         (browser access address)
```

### 4.2 Variable Reference

| Variable | Default Value | Config Location | Consumer Service |
|------|--------|----------|----------|
| `PPT_OPENAI_API_KEY` | — | `.env` | python-worker, gateway |
| `PPT_ANTHROPIC_API_KEY` | `""` | `.env` | python-worker |
| `PPT_LLM_PROVIDER` | `openai` | `.env` | python-worker |
| `PPT_LLM_MODEL` | `gpt-4o-mini` | `.env` | python-worker |
| `PPT_LLM_TEMPERATURE` | `0.3` | `.env` | python-worker |
| `BIND_ADDR` | `0.0.0.0:3000` | `docker-compose.yml` | gateway |
| `PYTHON_WORKER_URL` | `http://python-worker:8000` | `docker-compose.yml` | gateway |
| `QDRANT_URL` | `http://qdrant:6333` | `docker-compose.yml` | gateway, python-worker |
| `MAX_UPLOAD_SIZE` | `52428800` | `.env` | gateway |
| `RATE_LIMIT_PER_MINUTE` | `60` | `.env` | gateway |
| `VITE_API_BASE_URL` | `http://localhost:3000` | `docker-compose.yml` | frontend |

---

## 5. Qdrant Collection Initialization

### 5.1 Initialization Script

```python
# scripts/init_qdrant.py

COLLECTION_NAME = "user_preferences"

client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(
        size=768,                    # OpenAI text-embedding-3-small dimension
        distance=Distance.COSINE,    # Cosine similarity
        on_disk=True,                # Store vectors on disk
    ),
    hnsw_config=HnswConfigDiff(
        m=16,                        # HNSW graph connection count
        ef_construct=128,            # Build-time search depth
        full_scan_threshold=10000,   # Full scan threshold
    ),
    quantization_config=ScalarQuantization(
        scalar=ScalarQuantizationConfig(
            type="int8",               # INT8 quantization
            always_ram=True,           # Quantized vectors kept in RAM
        )
    ),
)

# Payload indexes
client.create_payload_index("user_id", {"type": "keyword", "is_tenant": True})
client.create_payload_index("preference_type", "keyword")
client.create_payload_index("created_at", "integer")
```

### 5.2 Collection Configuration

| Configuration Item | Value | Description |
|--------|-----|------|
| Vector dimension | 768 | OpenAI `text-embedding-3-small` |
| Distance metric | Cosine | Cosine similarity |
| Vector storage | `on_disk=True` | Save memory |
| HNSW `m` | 16 | Graph connectivity |
| HNSW `ef_construct` | 128 | Build quality |
| Quantization | INT8 Scalar | Compress to 1/4, controllable precision loss |
| `user_id` index | Keyword + Tenant | Enforced tenant isolation |
| `preference_type` index | Keyword | Type filtering |
| `created_at` index | Integer | Time range queries |

---

## 6. Health Check System

### 6.1 Check Matrix

| Service | Endpoint | Check Method | Interval | Timeout | Retries | Startup Grace Period |
|------|------|----------|------|------|------|----------|
| qdrant | `GET /healthz` | `curl -f` | 5s | 3s | 5 | — |
| python-worker | `GET /health` | `curl -f` | 5s | 3s | 5 | — |
| gateway | `GET /health` | `curl -f` | 5s | 3s | 5 | 5s |

### 6.2 Dependencies

```
+-------------------------------------------------------------------+
|                     Health Check Dependency Chain                  |
+-------------------------------------------------------------------+

  qdrant healthy
    |
    | condition: service_healthy
    v
  python-worker starts
    |
    | internal: wait for qdrant:6333/healthz (30s max)
    | internal: run init_qdrant.py
    | internal: start uvicorn
    v
  python-worker healthy
    |
    | condition: service_healthy
    v
  gateway starts
    |
    | internal: bind to 0.0.0.0:3000
    v
  gateway healthy
    |
    | (no condition, just depends_on)
    v
  frontend starts
```

---

## 7. Makefile Commands

| Command | Description | Execution |
|------|------|----------|
| `make up` | Start full stack | `docker compose up -d --build` |
| `make down` | Stop full stack | `docker compose down` |
| `make logs` | View logs | `docker compose logs -f` |
| `make build` | Build images | `docker compose build` |
| `make clean` | Clean up resources | `docker compose down -v` + delete temporary PPTX files |
| `make test` | Run unit tests | `pytest tests/` + `cargo test` |
| `make test-e2e` | Run E2E tests | `pytest tests/e2e/ -v` |

### 7.1 Development Workflow

```bash
# First-time startup
cp .env.example .env
# Edit .env and fill in PPT_OPENAI_API_KEY
make up

# View logs
make logs

# Hot reload after code changes
# - frontend: Vite HMR takes effect automatically
# - python-worker: uvicorn --reload takes effect automatically
# - gateway: requires rebuild

# Restart a single service
docker compose restart gateway

# Full reset (clear data)
make clean && make up
```

---

## 8. Docker-less Development Mode

### 8.1 Service Startup Commands

| Service | Command | Port |
|------|------|------|
| Qdrant | `docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:v1.11.0` | 6333/6334 |
| Python Worker | `cd python_worker && uvicorn api.main:app --reload --port 8000` | 8000 |
| Gateway | `cargo run` | 3000 |
| Frontend | `cd frontend && npm run dev` | 5173 |

### 8.2 Docker-less Environment Variables

```bash
export PPT_OPENAI_API_KEY="sk-xxx"
export PPT_LLM_PROVIDER="openai"
export PPT_LLM_MODEL="gpt-4o-mini"
export BIND_ADDR="0.0.0.0:3000"
export PYTHON_WORKER_URL="http://localhost:8000"
export QDRANT_URL="http://localhost:6333"
export MAX_UPLOAD_SIZE="52428800"
export RATE_LIMIT_PER_MINUTE="60"
```

---

## 9. Resource Requirements Estimate

### 9.1 Container Resources

| Service | CPU | Memory | Disk | Notes |
|------|-----|------|------|------|
| qdrant | 0.5-1 | 512MB-1GB | 1GB+ | Vector data persistence |
| python-worker | 0.5-1 | 512MB-1GB | 100MB | Primarily LLM API calls |
| gateway | 0.1-0.5 | 64-128MB | 50MB | Lightweight proxy |
| frontend | 0.1-0.5 | 256MB | 100MB | Vite dev server |

### 9.2 External Dependencies

| Service | Type | Quota Impact |
|------|------|----------|
| OpenAI API | Token-based billing | `text-embedding-3-small` + `gpt-4o-mini` |
| Anthropic API | Token-based billing | Optional, Claude models |

---

## 10. Production Environment Recommendations

### 10.1 Known Limitations (Current MVP)

| Limitation | Description | Recommendation |
|------|------|------|
| Frontend development mode | `npm run dev`, not a production build | Use `npm run build` + Nginx in production |
| Python Worker `--reload` | Development mode, lower performance | Remove `--reload` in production, use multiple workers |
| No HTTPS | Plain-text HTTP | Place Nginx/Traefik in front for TLS termination |
| No authentication | `x-user-id` plain-text header | Integrate OAuth/JWT |
| Single Gateway instance | No horizontal scaling | Place a load balancer in front |
| Single SSE broadcast channel | All clients share the same channel | Channel by task_id |
| Single-node Qdrant | No high availability | Use Qdrant cluster mode in production |

### 10.2 Recommended Production Deployment Topology

```
+-------------------------------------------------------------------+
|                  Recommended Production Deployment Topology        |
+-------------------------------------------------------------------+

  Internet
     |
     v
  +--------------------+
  |  Nginx / Traefik   |  TLS termination, static asset caching
  +---------+----------+
            |
      +-----+-----+
      |           |
      v           v
  +--------+  +--------------------+
  | Static |  |  Gateway (x3)      |  Load balancing
  | Assets |  |  Rust Axum         |
  +--------+  +---------+----------+
                        |
            +-----------+-----------+
            |                       |
            v                       v
  +--------------------+  +--------------------+
  |  Python Worker (x3)|  |  Qdrant Cluster    |
  |  FastAPI/Uvicorn   |  |  (3+ nodes)        |
  +--------------------+  +--------------------+
            |
            v
  +--------------------+
  |  OpenAI / Claude   |
  +--------------------+
```

### 10.3 Production Dockerfile Adjustments

**Frontend Production Build:**

```dockerfile
# Build stage
FROM node:20-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Runtime stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**Python Worker Production Runtime:**

```dockerfile
# Replace uvicorn --reload
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4"]
```

**Gateway Production Runtime:**

```dockerfile
# Existing HEALTHCHECK, recommended additions
ENV RUST_LOG=info
CMD ["./forge-ppt"]
```
