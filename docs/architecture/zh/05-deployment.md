# 部署架构

## 1. 部署拓扑

```
+=====================================================================+
|                     Docker Compose 部署拓扑                          |
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

### 1.1 服务依赖链

```
+-------------------------------------------------------------------+
|                     服务启动依赖链                                  |
+-------------------------------------------------------------------+

  qdrant (最先启动)
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
  frontend (最后启动)
```

---

## 2. Docker Compose 配置详解

### 2.1 服务定义

| 服务 | 镜像/构建 | 端口 | 依赖 |
|------|-----------|------|------|
| **qdrant** | `qdrant/qdrant:v1.11.0` | 6333, 6334 | — |
| **python-worker** | `python:3.11-slim` (自定义) | 8000 | qdrant (healthy) |
| **gateway** | `rust:1.80` → `debian:bookworm-slim` | 3000 | python-worker (healthy) |
| **frontend** | `node:20-slim` (自定义) | 5173 | gateway |

### 2.2 网络拓扑

```yaml
# Docker Compose 隐式创建 bridge 网络
networks:
  default:
    driver: bridge
    name: forge_default
```

**服务间 DNS 解析：**
| 源服务 | 目标服务 | 内网地址 |
|--------|----------|----------|
| frontend (Vite proxy) | gateway | `http://gateway:3000` |
| gateway | python-worker | `http://python-worker:8000` |
| gateway | qdrant | `http://qdrant:6333` |
| python-worker | qdrant | `http://qdrant:6333` |

### 2.3 数据卷

| 卷名 | 挂载点 | 用途 | 持久化 |
|------|--------|------|--------|
| `qdrant_storage` | `/qdrant/storage` | Qdrant 向量数据 | 是（named volume） |
| `pptx_uploads` | `/tmp/uploads` | PPTX 上传暂存 | 是（named volume） |
| `./frontend` | `/app` | 前端源码热重载 | 否（bind mount） |
| `./python_worker` | `/app` | Python 源码热重载 | 否（bind mount） |
| `/app/node_modules` | — | 排除 node_modules 覆盖 | 匿名卷 |

---

## 3. 各服务 Dockerfile

### 3.1 Gateway (Rust 多阶段构建)

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

**构建策略：**
1. **依赖缓存层**：先复制 `Cargo.toml`/`Cargo.lock`，构建 dummy main 以缓存依赖编译
2. **源码编译层**：复制 `src/` 和 `tests/`，强制重新编译（`touch src/main.rs`）
3. **运行时精简**：基于 `debian:bookworm-slim`，仅安装 `ca-certificates` 和 `curl`
4. **健康检查**：每 30s 检查 `/health`，启动期 5s 宽限

**镜像特性：**
- 多阶段构建，最终镜像不含 Rust 工具链
- 静态编译二进制（依赖 glibc，故用 Debian 而非 Alpine）
- 二进制路径：`/app/forge-ppt`

### 3.2 Python Worker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 系统依赖（python-pptx, lxml, cairo 等需要）
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libcairo2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY python_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY python_worker/ .
COPY scripts/init_qdrant.py /scripts/init_qdrant.py

# Entrypoint
COPY python_worker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
```

**Entrypoint 脚本逻辑：**

```bash
#!/bin/bash
set -e

# 1. 等待 Qdrant 就绪（最多 30 秒）
for i in {1..30}; do
    if curl -sf http://qdrant:6333/healthz; then
        break
    fi
    sleep 1
done

# 2. 初始化 Qdrant 集合
python3 /scripts/init_qdrant.py || true

# 3. 启动 FastAPI 服务
exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**启动时序：**
1. Docker Compose 等待 `qdrant` 健康检查通过
2. `python-worker` 容器启动，执行 `entrypoint.sh`
3. `entrypoint.sh` 内部再次轮询 Qdrant（30 次，间隔 1s）
4. 运行 `init_qdrant.py` 创建/确认 `user_preferences` 集合
5. 启动 `uvicorn`（`--reload` 开发模式）

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

**构建策略：**
- 基于 `node:20-slim`
- 开发模式运行：`npm run dev -- --host 0.0.0.0`
- 暴露 5173 供外部访问
- 通过 bind mount `./frontend:/app` 实现源码热重载
- `node_modules` 通过匿名卷保护，防止 bind mount 覆盖

### 3.4 Qdrant (官方镜像)

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

## 4. 环境变量映射

### 4.1 变量传递链

```
+-------------------------------------------------------------------+
|                  环境变量传递链                                      |
+-------------------------------------------------------------------+

  .env 文件 (Host)
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
  PPT_OPENAI_API_KEY=${PPT_OPENAI_API_KEY}      (透传)
  PPT_ANTHROPIC_API_KEY=${PPT_ANTHROPIC_API_KEY} (透传)
  PPT_LLM_PROVIDER=${PPT_LLM_PROVIDER:-openai}   (默认值)
  PPT_LLM_MODEL=${PPT_LLM_MODEL:-gpt-4o-mini}    (默认值)
  PPT_LLM_TEMPERATURE=${PPT_LLM_TEMPERATURE:-0.3}(默认值)
  QDRANT_URL=http://qdrant:6333                   (硬编码内网地址)

  gateway
  =======
  BIND_ADDR=0.0.0.0:3000                          (硬编码)
  PYTHON_WORKER_URL=http://python-worker:8000     (硬编码内网地址)
  QDRANT_URL=http://qdrant:6333                   (硬编码内网地址)
  PPT_OPENAI_API_KEY=${PPT_OPENAI_API_KEY}        (透传)
  MAX_UPLOAD_SIZE=${MAX_UPLOAD_SIZE:-52428800}    (默认值)
  RATE_LIMIT_PER_MINUTE=${RATE_LIMIT_PER_MINUTE:-60} (默认值)

  frontend
  ========
  VITE_API_BASE_URL=http://localhost:3000         (浏览器访问地址)
```

### 4.2 变量说明

| 变量 | 默认值 | 配置位置 | 消费服务 |
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

## 5. Qdrant 集合初始化

### 5.1 初始化脚本

```python
# scripts/init_qdrant.py

COLLECTION_NAME = "user_preferences"

client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(
        size=768,                    # OpenAI text-embedding-3-small 维度
        distance=Distance.COSINE,    # Cosine 相似度
        on_disk=True,                # 向量存储在磁盘
    ),
    hnsw_config=HnswConfigDiff(
        m=16,                        # HNSW 图连接数
        ef_construct=128,            # 构建时搜索深度
        full_scan_threshold=10000,   # 全表扫描阈值
    ),
    quantization_config=ScalarQuantization(
        scalar=ScalarQuantizationConfig(
            type="int8",               # INT8 量化
            always_ram=True,           # 量化后的向量常驻内存
        )
    ),
)

# Payload 索引
client.create_payload_index("user_id", {"type": "keyword", "is_tenant": True})
client.create_payload_index("preference_type", "keyword")
client.create_payload_index("created_at", "integer")
```

### 5.2 集合配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 向量维度 | 768 | OpenAI `text-embedding-3-small` |
| 距离度量 | Cosine | 余弦相似度 |
| 向量存储 | `on_disk=True` | 节省内存 |
| HNSW `m` | 16 | 图连通度 |
| HNSW `ef_construct` | 128 | 构建质量 |
| 量化 | INT8 Scalar | 压缩至 1/4，精度损失可控 |
| `user_id` 索引 | Keyword + Tenant | 强制租户隔离 |
| `preference_type` 索引 | Keyword | 类型过滤 |
| `created_at` 索引 | Integer | 时间范围查询 |

---

## 6. 健康检查体系

### 6.1 检查矩阵

| 服务 | 端点 | 检查方式 | 间隔 | 超时 | 重试 | 启动宽限 |
|------|------|----------|------|------|------|----------|
| qdrant | `GET /healthz` | `curl -f` | 5s | 3s | 5 | — |
| python-worker | `GET /health` | `curl -f` | 5s | 3s | 5 | — |
| gateway | `GET /health` | `curl -f` | 5s | 3s | 5 | 5s |

### 6.2 依赖关系

```
+-------------------------------------------------------------------+
|                     健康检查依赖链                                  |
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

## 7. Makefile 命令

| 命令 | 说明 | 执行内容 |
|------|------|----------|
| `make up` | 启动全栈 | `docker compose up -d --build` |
| `make down` | 停止全栈 | `docker compose down` |
| `make logs` | 查看日志 | `docker compose logs -f` |
| `make build` | 构建镜像 | `docker compose build` |
| `make clean` | 清理资源 | `docker compose down -v` + 删除临时 PPTX |
| `make test` | 运行单元测试 | `pytest tests/` + `cargo test` |
| `make test-e2e` | 运行 E2E 测试 | `pytest tests/e2e/ -v` |

### 7.1 开发工作流

```bash
# 首次启动
cp .env.example .env
# 编辑 .env 填入 PPT_OPENAI_API_KEY
make up

# 查看日志
make logs

# 修改代码后热重载
# - frontend: Vite HMR 自动生效
# - python-worker: uvicorn --reload 自动生效
# - gateway: 需要重新构建

# 重启单个服务
docker compose restart gateway

# 完全重置（清空数据）
make clean && make up
```

---

## 8. 无 Docker 开发模式

### 8.1 服务启动命令

| 服务 | 命令 | 端口 |
|------|------|------|
| Qdrant | `docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:v1.11.0` | 6333/6334 |
| Python Worker | `cd python_worker && uvicorn api.main:app --reload --port 8000` | 8000 |
| Gateway | `cargo run` | 3000 |
| Frontend | `cd frontend && npm run dev` | 5173 |

### 8.2 无 Docker 环境变量

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

## 9. 资源需求估算

### 9.1 容器资源

| 服务 | CPU | 内存 | 磁盘 | 说明 |
|------|-----|------|------|------|
| qdrant | 0.5-1 | 512MB-1GB | 1GB+ | 向量数据持久化 |
| python-worker | 0.5-1 | 512MB-1GB | 100MB | LLM API 调用为主 |
| gateway | 0.1-0.5 | 64-128MB | 50MB | 轻量代理 |
| frontend | 0.1-0.5 | 256MB | 100MB | Vite dev server |

### 9.2 外部依赖

| 服务 | 类型 | 配额影响 |
|------|------|----------|
| OpenAI API | 按 Token 计费 | `text-embedding-3-small` + `gpt-4o-mini` |
| Anthropic API | 按 Token 计费 | 可选，Claude 模型 |

---

## 10. 生产环境建议

### 10.1 已知限制（当前 MVP）

| 限制 | 说明 | 建议 |
|------|------|------|
| 前端开发模式 | `npm run dev`，非生产构建 | 生产用 `npm run build` + Nginx |
| Python Worker `--reload` | 开发模式，性能较低 | 生产去掉 `--reload`，用多个 worker |
| 无 HTTPS | 明文 HTTP | 前置 Nginx/Traefik 终止 TLS |
| 无身份认证 | `x-user-id` 明文头部 | 接入 OAuth/JWT |
| 单实例 Gateway | 无水平扩展 | 前置负载均衡 |
| SSE 单广播通道 | 所有客户端共享同一通道 | 按 task_id 分通道 |
| Qdrant 单节点 | 无高可用 | 生产用 Qdrant 集群模式 |

### 10.2 生产部署拓扑（建议）

```
+-------------------------------------------------------------------+
|                  建议生产部署拓扑                                    |
+-------------------------------------------------------------------+

  Internet
     |
     v
  +--------------------+
  |  Nginx / Traefik   |  TLS 终止, 静态资源缓存
  +---------+----------+
            |
      +-----+-----+
      |           |
      v           v
  +--------+  +--------------------+
  | Static |  |  Gateway (x3)      |  负载均衡
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

### 10.3 生产 Dockerfile 调整

**Frontend 生产构建：**

```dockerfile
# 构建阶段
FROM node:20-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# 运行阶段
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**Python Worker 生产运行：**

```dockerfile
# 替换 uvicorn --reload
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4"]
```

**Gateway 生产运行：**

```dockerfile
# 已有 HEALTHCHECK，建议增加
ENV RUST_LOG=info
CMD ["./forge-ppt"]
```
