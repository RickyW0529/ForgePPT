# 04 · 记忆系统（Memory System）

> 按你给的分层架构落地：基础设施层 / 记忆类型层 / 存储后端层 / 嵌入服务层。

---

## 1. 设计目标

1. **多类型**：覆盖工作 / 情景 / 语义 / 感知四类记忆。
2. **可插拔后端**：Qdrant（向量）/ Neo4j（图）/ SQLite（文档）任选组合。
3. **零拷贝读取**：上层只用 `MemoryManager`，不感知后端。
4. **嵌入解耦**：嵌入服务从存储中独立，可换成本地模型。
5. **MVP 可裁剪**：MVP 只用 Working + Episodic + Qdrant + SQLite + DashScope。

---

## 2. 分层架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Application Layer (Agent / Planner)                 │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ recall() / store() / forget()
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│        Infrastructure Layer                                          │
│  ┌──────────────┐  ┌────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │MemoryManager │  │ MemoryItem │  │ MemoryConfig │  │BaseMemory │ │
│  └──────┬───────┘  └────────────┘  └──────────────┘  └───────────┘ │
└─────────┼───────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│        Memory Types Layer                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │WorkingMemory │  │EpisodicMemory│  │SemanticMem  │  │Perceptual│ │
│  │  (TTL, RAM)  │  │ (time-series)│  │ (graph KB)  │  │  (multi- │ │
│  │              │  │              │  │             │  │  modal)  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘  └────┬─────┘ │
└─────────┼─────────────────┼─────────────────┼──────────────┼───────┘
          │                 │                 │              │
          ▼                 ▼                 ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│        Storage Backend Layer                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ Qdrant       │  │ Neo4j        │  │ SQLite                  │   │
│  │ (vector)     │  │ (graph)      │  │ (document, full-text)   │   │
│  └──────────────┘  └──────────────┘  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│        Embedding Service Layer                                       │
│  ┌──────────────┐  ┌────────────────────┐  ┌───────────────────┐   │
│  │  DashScope   │  │ LocalTransformer   │  │     TFIDF         │   │
│  │  (cloud)     │  │ (sentence-transf.) │  │   (fallback)      │   │
│  └──────────────┘  └────────────────────┘  └───────────────────┘   │
│           （统一经由 ProviderRouter.embed() 调用，见 03）              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 基础设施层

### 3.1 MemoryItem（标准数据结构）

```python
class MemoryItem(BaseModel):
    item_id: str                          # UUID
    user_id: str                          # 隔离单位
    workflow_id: str | None = None        # 关联工作流（情景记忆）
    type: Literal["working", "episodic", "semantic", "perceptual"]

    content: str                          # 文本表示（必填，用于嵌入）
    payload: dict = {}                    # 结构化负载
    modality: Literal["text", "image", "audio", "mixed"] = "text"

    embedding: list[float] | None = None  # 由 EmbeddingService 填充
    embedding_model: str | None = None

    tags: list[str] = []
    importance: float = 0.5               # 0..1，影响保留 / 召回排序
    confidence: float = 1.0               # 来源可信度

    created_at: datetime
    accessed_at: datetime
    expires_at: datetime | None = None    # TTL（Working 必填）
    source: str                           # "user_feedback" | "agent_observation" | ...
```

### 3.2 MemoryConfig

```python
class MemoryConfig(BaseModel):
    working_ttl_sec: int = 3600
    working_capacity: int = 200           # LRU 上限
    episodic_retention_days: int = 90
    semantic_min_confidence: float = 0.7  # 低于此值不进语义层
    embedding_dim: int = 768
    default_top_k: int = 5
    score_threshold: float = 0.55
```

### 3.3 BaseMemory（抽象）

```python
class BaseMemory(Protocol):
    type: str

    async def store(self, item: MemoryItem) -> str: ...
    async def recall(self, query: MemoryQuery) -> list[MemoryRecall]: ...
    async def update(self, item_id: str, patch: dict) -> None: ...
    async def forget(self, item_id: str) -> None: ...
    async def stats(self) -> MemoryStats: ...

class MemoryQuery(BaseModel):
    user_id: str
    text: str | None = None               # 语义查询
    tags: list[str] = []
    filters: dict = {}                    # payload 字段精确过滤
    top_k: int = 5
    score_threshold: float | None = None
    time_range: tuple[datetime, datetime] | None = None

class MemoryRecall(BaseModel):
    item: MemoryItem
    score: float                          # 0..1
    explanation: str | None = None
```

### 3.4 MemoryManager（统一入口）

```python
class MemoryManager:
    def __init__(self, config: MemoryConfig,
                 working: WorkingMemory,
                 episodic: EpisodicMemory,
                 semantic: SemanticMemory | None = None,
                 perceptual: PerceptualMemory | None = None,
                 embedder: EmbeddingService): ...

    async def remember(self, item: MemoryItem) -> str:
        """路由到对应 type 的 Memory，并按需嵌入。"""

    async def recall(self, query: MemoryQuery,
                     across: list[str] = ["working", "episodic", "semantic"]
                    ) -> list[MemoryRecall]:
        """跨记忆类型联合召回，合并后重排。"""

    async def consolidate(self, user_id: str) -> ConsolidationReport:
        """从 Episodic 中抽取高频高重要事实 → Semantic。Phase 3。"""

    async def forget(self, item_id: str) -> None: ...
```

**关键 API**：
- `remember` 由 Agent / Reflection 写入。
- `recall` 由 Context Engineering（06）拼上下文时调用。
- `consolidate` 由后台 Job 周期触发。

---

## 4. 记忆类型层

### 4.1 WorkingMemory（工作记忆）

**特点**：进程内 / Redis（可选），TTL 短，容量小。

```python
class WorkingMemory(BaseMemory):
    type = "working"

    def __init__(self, backend: Literal["inproc", "redis"] = "inproc",
                 ttl_sec: int = 3600,
                 capacity: int = 200): ...
```

- 后端：MVP 用进程内 dict + heapq；Phase 2 上 Redis。
- 用途：当前 workflow 内的临时事实，如「这次用户希望整体偏蓝」。
- 召回方式：纯精确匹配 + LRU 排序（不嵌入）。

### 4.2 EpisodicMemory（情景记忆）

**特点**：完整事件流水，按时间存档。

- 后端：**SQLite 文档存储**（结构化）+ **Qdrant 向量索引**（语义查询）。
- 一个 `MemoryItem` 在 SQLite 全量存，向量在 Qdrant 存 `item_id ↔ embedding`。
- 用途：用户过去和 Agent 的每次交互。
- 召回方式：语义召回 + 时间窗过滤。

```python
class EpisodicMemory(BaseMemory):
    type = "episodic"

    def __init__(self, doc_store: SQLiteDocumentStore,
                 vector_store: QdrantVectorStore,
                 embedder: EmbeddingService): ...
```

### 4.3 SemanticMemory（语义记忆，Phase 3）

**特点**：抽象事实，图谱化。

- 后端：**Neo4j**。节点 = 实体（User、Style、Brand、Page），边 = 关系（PREFERS、AVOIDS、USES）。
- 来源：从 Episodic 通过 `consolidate()` 抽取，或从用户显式偏好导入。
- 用途：长期偏好画像、品牌守则、跨 workflow 知识。

```python
class SemanticMemory(BaseMemory):
    type = "semantic"

    async def add_fact(self, subject, predicate, object, confidence) -> None: ...
    async def query_facts(self, subject=None, predicate=None) -> list[Fact]: ...
    async def ask(self, cypher: str) -> Any: ...   # 高级查询
```

### 4.4 PerceptualMemory（感知记忆，Phase 3）

**特点**：多模态（图片、SVG、表格快照）。

- 后端：**Qdrant**（图像嵌入，CLIP 类）+ **SQLite**（原图引用、metadata）。
- 用途：让 Agent 「记住」过去生成的好看 SVG / 配色样张，未来可以复用。
- 召回：多模态相似度（图 → 图，文 → 图）。

---

## 5. 存储后端层

### 5.1 QdrantVectorStore

```python
class QdrantVectorStore:
    def __init__(self, url: str, collection_prefix: str = "fppt"): ...

    async def upsert(self, collection: str, item_id: str,
                     vector: list[float], payload: dict) -> None: ...

    async def search(self, collection: str, vector: list[float],
                     top_k: int, filter: dict | None = None) -> list[Hit]: ...

    async def delete(self, collection: str, item_id: str) -> None: ...
```

- 已在项目里启动（docker compose）。MVP 直接复用。
- collection 命名：`fppt_episodic`, `fppt_perceptual_image` 等。

### 5.2 Neo4jGraphStore

```python
class Neo4jGraphStore:
    async def merge_node(self, label: str, props: dict, key: str) -> str: ...
    async def merge_edge(self, src_id, dst_id, type: str, props: dict) -> None: ...
    async def query(self, cypher: str, params: dict) -> list[dict]: ...
```

Phase 3 引入；MVP 不依赖。

### 5.3 SQLiteDocumentStore

```python
class SQLiteDocumentStore:
    async def insert(self, table: str, doc: dict) -> str: ...
    async def get(self, table: str, item_id: str) -> dict | None: ...
    async def query(self, table: str, where: dict,
                    order_by: str = None, limit: int = None) -> list[dict]: ...
    async def full_text_search(self, table: str, q: str) -> list[dict]: ...   # FTS5
```

- 单文件 `data/memory.db`，启动时初始化。
- FTS5 提供文本回退检索（当向量服务挂了时）。

---

## 6. 嵌入服务层

### 6.1 EmbeddingService（统一接口）

```python
class EmbeddingService:
    def __init__(self, router: ProviderRouter, dim: int = 768): ...

    async def embed(self, texts: list[str],
                    purpose: Literal["episodic", "semantic", "perceptual"] = "episodic"
                   ) -> list[list[float]]:
        return await self.router.embed(texts, purpose=purpose)
```

**所有嵌入调用走 `ProviderRouter.embed()`**（03 中定义），由 router 负责选 DashScope / OpenAI / 本地。

### 6.2 三档配置

| Tier | Provider | 维度 | 场景 |
|---|---|---|---|
| 1 | DashScope text-embedding-v3 | 1024（截 768） | 主用，中文 |
| 1' | OpenAI text-embedding-3-small | 1536（截 768） | 国际备份 |
| 2 | sentence-transformers `bge-small-zh` | 512（升 768 用 padding 或换 collection） | 离线 |
| 3 | scikit-learn TFIDF | 自适应 | 完全断网 |

**维度统一**：MVP 用 768 维（与现有 Qdrant collection 一致）。Tier 间维度差异由 EmbeddingService 内部 normalize / project。

### 6.3 缓存

EmbeddingService 内置 LRU 缓存（key = `sha256(text+model)`），避免相同文本重复嵌入。

---

## 7. 数据迁移

| 类型 | 操作 | 触发 |
|---|---|---|
| Working → Episodic | TTL 到期前若 importance > 0.7，转 Episodic | TTL 清理时 |
| Episodic → Semantic | `consolidate()`：从重复 ≥3 次的事件抽事实 | 每天定时 |
| Semantic ← User Edit | 用户在 UI 显式修改偏好 | 实时 |
| Perceptual ← Workflow | 用户标记「这页好看」时入库 | UI 触发 |

---

## 8. 在 Agent 流程中的应用

### 8.1 Planner Context 注入（06 详）

```python
memories = await memory_manager.recall(
    MemoryQuery(
        user_id=ctx.user_id,
        text=user_prompt,
        top_k=3,
        score_threshold=0.55,
    ),
    across=["semantic", "episodic"],
)
planner_context.memory_snippets = [m.item.content for m in memories]
```

### 8.2 Reflector 写入

```python
await memory_manager.remember(
    MemoryItem(
        type="episodic",
        content=f"User asked '{prompt}'. Plan v{plan_v} failed: {reason}",
        tags=["agent_failure", role],
        importance=0.6,
        source="reflector",
    )
)
```

### 8.3 用户反馈写入

```python
# 用户点「应用」按钮时
await memory_manager.remember(
    MemoryItem(
        type="episodic",
        content=f"User accepted theme change: {summary}",
        tags=["user_accept"],
        importance=0.9,
    )
)
```

---

## 9. 隐私与合规

- 所有 MemoryItem 必有 `user_id`，跨用户严格隔离。
- 提供 `forget_user(user_id)` 一键清除。
- Semantic 层导出时显示来源 trace，可逆向追溯。
- 不嵌入用户敏感字段（手机号、邮箱）—— Agent 调 `remember` 前先脱敏。

---

## 10. 一致性与并发

- Working 是单进程的，无一致性问题。
- Episodic 用 SQLite 事务 + Qdrant upsert，**双写**最终一致：先写 SQLite，再 upsert Qdrant；写 Qdrant 失败时设标志 `embedding_pending=true`，后台 job 重试。
- Semantic 用 Neo4j 事务。

---

## 11. 测试要求

- MemoryItem schema 单测。
- 每个 Memory 类型：store + recall + forget 闭环测试。
- MemoryManager：多类型联合召回的合并排序。
- EmbeddingService：mock router，断言传参正确。
- TFIDF fallback：断网场景测试。

---

## 12. Phasing

| 阶段 | 启用 |
|---|---|
| **MVP** | WorkingMemory（inproc）+ EpisodicMemory（SQLite + Qdrant）+ DashScope embedding + TFIDF fallback |
| Phase 2 | + LocalTransformer embedding；EpisodicMemory 接入 Planner Context |
| Phase 3 | + SemanticMemory（Neo4j）+ PerceptualMemory + consolidate Job |
| Future | 联邦化（多用户偏好聚类做行业模板） |

---

## 13. 待决策

1. **MVP 是否启用 Episodic？** 倾向**启用**（仅 store 不召回），先攒数据；召回到 Phase 2。
2. **Embedding 维度统一**：是否一开始就用 1024？需要换 Qdrant collection。倾向**先沿用 768，Phase 3 再扩**。
3. **Neo4j 是否必要？** 如果只做简单偏好，SQLite 也能存。但用户原架构里有 Neo4j，且语义图谱用 Cypher 更自然——Phase 3 启用。
4. **用户隔离**：MVP 单用户够吗？现状 ForgePPT 没有 auth 体系，倾向 MVP 用 `user_id="default"`，等 auth 体系建好再分用户。
