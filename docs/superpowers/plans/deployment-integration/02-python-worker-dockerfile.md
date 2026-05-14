# 02 - Python Worker Dockerfile

**Files:**
- Create: `python_worker/Dockerfile`
- Create: `python_worker/entrypoint.sh`

---

- [ ] **Step 1: Build and verify**

```dockerfile
# python_worker/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for python-pptx and cairo
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libcairo2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY python_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY python_worker/ .
COPY scripts/init_qdrant.py /scripts/init_qdrant.py

# Copy entrypoint
COPY python_worker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
```

```bash
#!/bin/bash
# python_worker/entrypoint.sh
set -e

# Wait for Qdrant to be ready
echo "Waiting for Qdrant..."
for i in {1..30}; do
    if curl -sf http://qdrant:6333/healthz > /dev/null 2>&1; then
        echo "Qdrant is ready"
        break
    fi
    sleep 1
done

# Initialize Qdrant collection
echo "Initializing Qdrant collection..."
python3 /scripts/init_qdrant.py || true

# Start the FastAPI server
echo "Starting Python worker..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

- [ ] **Step 2: Test build**

Run: `docker compose build python-worker`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add python_worker/Dockerfile python_worker/entrypoint.sh
git commit -m "feat: add Python worker Dockerfile and entrypoint"
```
