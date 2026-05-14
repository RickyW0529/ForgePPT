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
