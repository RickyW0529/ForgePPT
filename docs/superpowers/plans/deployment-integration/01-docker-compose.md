# 01 - Docker Compose Orchestration

**Files:**
- Modify: `docker-compose.yml`
- Create: `.env.example`
- Create: `Makefile`

---

- [ ] **Step 1: Write docker-compose.yml**

```yaml
# docker-compose.yml
services:
  qdrant:
    image: qdrant/qdrant:v1.11.0
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_storage:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 5s
      timeout: 3s
      retries: 5

  python-worker:
    build:
      context: .
      dockerfile: python_worker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - PPT_LLM_PROVIDER=${PPT_LLM_PROVIDER:-openai}
      - PPT_LLM_MODEL=${PPT_LLM_MODEL:-gpt-4o-mini}
      - PPT_LLM_TEMPERATURE=${PPT_LLM_TEMPERATURE:-0.3}
      - PPT_OPENAI_API_KEY=${PPT_OPENAI_API_KEY}
      - PPT_ANTHROPIC_API_KEY=${PPT_ANTHROPIC_API_KEY}
      - QDRANT_URL=http://qdrant:6333
    volumes:
      - ./python_worker:/app
      - pptx_uploads:/tmp/uploads
    depends_on:
      qdrant:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 5s
      timeout: 3s
      retries: 5

  gateway:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - BIND_ADDR=0.0.0.0:3000
      - PYTHON_WORKER_URL=http://python-worker:8000
      - QDRANT_URL=http://qdrant:6333
      - PPT_OPENAI_API_KEY=${PPT_OPENAI_API_KEY}
      - MAX_UPLOAD_SIZE=${MAX_UPLOAD_SIZE:-52428800}
      - RATE_LIMIT_PER_MINUTE=${RATE_LIMIT_PER_MINUTE:-60}
    depends_on:
      python-worker:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 5s
      timeout: 3s
      retries: 5

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    environment:
      - VITE_API_BASE_URL=http://localhost:3000
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - gateway

volumes:
  qdrant_storage:
  pptx_uploads:
```

- [ ] **Step 2: Write .env.example**

```bash
# .env.example
# LLM Configuration
PPT_LLM_PROVIDER=openai
PPT_LLM_MODEL=gpt-4o-mini
PPT_LLM_TEMPERATURE=0.3
PPT_OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PPT_ANTHROPIC_API_KEY=

# Gateway Configuration
MAX_UPLOAD_SIZE=52428800
RATE_LIMIT_PER_MINUTE=60

# Qdrant (optional override)
# QDRANT_URL=http://localhost:6333
```

- [ ] **Step 3: Write Makefile**

```makefile
# Makefile
.PHONY: up down test logs build clean

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd python_worker && pytest tests/ -v
	cargo test

test-e2e:
	pytest tests/e2e/ -v

build:
	docker compose build

clean:
	docker compose down -v
	rm -rf python_worker/tests/fixtures/output_*.pptx
	rm -rf python_worker/tests/fixtures/round_trip.pptx
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .env.example Makefile
git commit -m "feat: add Docker Compose orchestration and Makefile"
```
