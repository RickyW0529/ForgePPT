# python_worker/Dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies for python-pptx and cairo
RUN sed -i 's|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g; s|http://deb.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list 2>/dev/null || true \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
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
