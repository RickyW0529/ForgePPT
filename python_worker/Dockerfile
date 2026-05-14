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
