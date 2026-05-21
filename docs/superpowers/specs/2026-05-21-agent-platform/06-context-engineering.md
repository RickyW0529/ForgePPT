# 06 · 上下文工程（Context Engineering）

> 给每个 LLM 调用「喂多少、喂什么」的工程化方法。是 Plan-Solve 能否真正 work 的关键。

---

## 1. 设计原则

1. **分层喂养**：不同角色（Planner / Reflector / Tool 内部）看到不同粒度的上下文。
2. **预算驱动**：每次调用先算 token 预算，再决定纳入哪些内容。
3. **摘要优先，原文按需**：默认给 LLM 看摘要，需要原文时通过工具（`ppt_inspect_slide`）主动拉取。
4. **稳定可重现**：相同输入产出相同 context（用于缓存与回放）。
5. **可压缩**：超预算时按优先级裁剪而不是直接报错。

---

## 2. 三层上下文模型

```
                  ┌────────────────────────────────────────┐
                  │   Tier 1 — Planner Context             │
                  │   ≤ 2K tokens（保证规模无关）           │
                  │   slide digests + tool manifests +     │
                  │   memory snippets + user prompt        │
                  └────────────────────────────────────────┘
                                    │
                                    ▼ Planner 决定要不要细看
                  ┌────────────────────────────────────────┐
                  │   Tier 2 — On-demand Drill-down        │
                  │   ≤ 1K tokens per call                 │
                  │   Planner 通过 ppt_inspect_slide 取细节  │
                  │   或 Solver 内部小 LLM 看 textbox 原文   │
                  └────────────────────────────────────────┘
                                    │
                                    ▼ Retry / Reflection 时
                  ┌────────────────────────────────────────┐
                  │   Tier 3 — Failure Feedback            │
                  │   ≤ 500 tokens                         │
                  │   previous_plan + failures + diff      │
                  └────────────────────────────────────────┘
```

---

## 3. Tier 1：Planner Context

### 3.1 内容结构

```python
class PlannerContext(BaseModel):
    deck_meta: DeckMeta
    slides_in_scope: list[SlideDigest]
    available_tools: list[ToolManifest]
    role_system_prompt: str
    user_prompt: str
    memory_snippets: list[MemorySnippet] = []
    previous_attempts: list[PlanFailure] = []
    constraints: PlanningConstraints
```

### 3.2 SlideDigest 构造算法

```python
def build_slide_digest(slide: Slide, sample_chars: int = 60) -> SlideDigest:
    text_boxes = [e for e in slide.elements if e.element_type == "textbox"]
    title = text_boxes[0].content[:30] if text_boxes else ""

    sample = " | ".join(
        tb.content[:sample_chars] for tb in text_boxes[:3]
    ) if sample_chars > 0 else None

    return SlideDigest(
        page_num=slide.page_num,
        title=title,
        sample_text=sample,
        text_count=len(text_boxes),
        image_count=len([e for e in slide.elements if e.element_type == "image"]),
        dominant_colors=_extract_colors(text_boxes, top_k=2),
        text_ids=[tb.text_id for tb in text_boxes],
    )
```

**控制参数**：
- `sample_chars`：每个 slide 抽样字符数。默认 60；可按 deck 大小动态降级。
- `dominant_colors`：从 textbox.style.font_color 统计 top-2。

### 3.3 动态预算分配

```python
def allocate_tier1_budget(deck_size: int, scope_size: int, total_budget: int = 2000) -> dict:
    # 固定开销
    fixed = 400                            # system prompt + structural overhead
    tools = 300                            # tool manifests
    memory = 200                           # memory snippets

    remaining = total_budget - fixed - tools - memory
    per_slide = max(15, remaining // max(scope_size, 1))

    return {
        "per_slide_tokens": per_slide,
        "sample_chars": min(60, per_slide * 3),  # 1 token ≈ 0.3 字
    }
```

50 页全 scope 时，per_slide 退化为 ~20 tokens，sample_chars 自动降到 ~10 字，但 title 保留。

### 3.4 工具清单注入

把 `ToolManifest`（02 定义）序列化成给 LLM 看的简洁形式：

```json
[
  {
    "name": "ppt_apply_style",
    "what": "Change text color, font size, bold for selected slides or text_ids",
    "params_schema": { "font_color": "string?", "font_size_multiplier": "number?", "bold": "boolean?" },
    "example": "{ \"slide_number\": 3, \"font_color\": \"#0F2A5C\" }"
  }
]
```

每个工具开销控制在 80-120 tokens。

### 3.5 Memory 注入

```python
class MemorySnippet(BaseModel):
    content: str            # ≤ 50 字
    relevance: float
    source_type: Literal["semantic", "episodic", "working"]
```

Phase 2 引入。MVP 阶段 `memory_snippets=[]`。

注入规则：
- top_k=3，按 score 排序
- 总长度 ≤ 200 tokens
- 在 prompt 中分块标记 `[USER_PREFERENCE]`, `[PAST_EXAMPLE]`

---

## 4. Tier 2：On-demand Drill-down

Tier 1 让 Planner「**看到全貌**」，Tier 2 让具体决策时「**看到细节**」。

### 4.1 路径 A：Planner 主动拉

Planner 把 `ppt_inspect_slide` 列入 plan 的 step（不写状态），Solver 执行时返回原文给 Reflector / 下一轮 Planner。

适合场景：用户 prompt 模糊，Planner 觉得「看了第 3 页才能决定」。

### 4.2 路径 B：Solver 内部小 LLM（最常用）

工具自己内部跑「小 LLM」，仅看自己负责的那个 textbox 原文。

```python
# inside ppt_apply_text tool
async def execute(self, ppt_state, params, target, ctx):
    for text_id in target.text_ids:
        original = ppt_state.get_text(text_id)
        # Tier 2 context for this small call:
        prompt = build_text_refine_context(
            original=original,
            instruction=params.instruction,
            style_hint=params.style_hint,
        )
        new_content = await ctx.llm_provider.call(LLMRequest(
            messages=prompt,
            metadata=RequestMetadata(purpose="solver_inner", ...),
        ))
        ...
```

Tier 2 context 通常 < 500 tokens（一个 textbox 不超过 1000 字）。

---

## 5. Tier 3：Failure Feedback（Retry / Reflection）

只在 retry 时启用。

### 5.1 结构

```python
class FailureFeedback(BaseModel):
    previous_plan_summary: str             # ≤ 100 tokens
    failures: list[PlanFailure]            # 已截断，最多 5 条
    state_diff: StateDiffDigest | None     # Solver 跑完后才有
    reflection: Reflection | None
```

### 5.2 注入位置

直接在 Planner system prompt 后追加一个 `<FEEDBACK>` 块：

```
<FEEDBACK>
你上一轮的计划没有完全成功：
- 第 2 步 (ppt_apply_style, slide_number=99) 失败：slide_number 越界（合法范围 [1, 3]）
- 第 4 步 (ppt_apply_text, text_id=t-xxx) 失败：text_id 不存在

请基于以上反馈修正后输出新计划。
</FEEDBACK>
```

### 5.3 截断策略

- failures > 5：保留前 3 + 后 2，中间用 `... (5 more) ...`。
- state_diff 用 `StateDiffDigest`（只列改了哪些 page_num，不展开内容）。

---

## 6. StateDiffDigest

跨节点 / 跨 retry 描述「状态变化」的紧凑表示：

```python
class StateDiffDigest(BaseModel):
    pages_changed: list[int]
    text_ids_changed: list[str]
    style_summary: dict                    # 各 page 平均 color 变化
    elements_added: int = 0
    elements_removed: int = 0

def compute_state_diff(before: PPTState, after: PPTState) -> StateDiffDigest: ...
```

约 50-150 tokens。用于：
- Reflection 输入
- Merge planner（看每个 branch 改了什么）
- SSE event

---

## 7. Token 预算总览

| 调用 | 输入预算 | 输出预算 | 说明 |
|---|---|---|---|
| Planner（首次） | 2000 | 1200 | Plan JSON |
| Planner（retry） | 2200 | 1200 | +200 失败反馈 |
| Reflector | 1500 | 400 | observation + decision |
| Solver-inner（per textbox） | 600 | 400 | refine 一段文字 |
| Merge planner | 1500 | 800 | merge plan |

总配额：单 Agent 节点不超过 10K tokens；单 workflow 不超过 40K tokens。Budget 由 03 ProviderRouter 统一管控。

---

## 8. 缓存策略

context 是相同输入 → 相同输出，可缓存：

```python
cache_key = sha256(
    canonical_json({
        "tier": "planner",
        "scope": sorted(scope),
        "deck_digest_hash": hash_digest(slides_in_scope),
        "user_prompt": user_prompt,
        "tools_version": tools_version,
        "memory_snippets_hash": hash([m.content for m in memory_snippets]),
        "previous_attempts": previous_attempts,
    })
)
```

缓存命中直接返回 plan，跳过 Planner LLM。

MVP 不做；Phase 2 启用。

---

## 9. 摘要质量保证

`SlideDigest.title` 取首 textbox 文字未必是真"标题"。改进策略（Phase 2）：

- 启发式：第一个 textbox 通常是 title，但若字号最大的 textbox 在中部，用最大字号那个。
- 视觉特征：在 parser 阶段标注 `placeholder_type=title/body/footer`（python-pptx 支持）。
- LLM 二次摘要（贵，仅 user_prompt 不明确时使用）。

MVP 用首 textbox 即可。

---

## 10. 上下文构造器（Context Builders）

集中放在 `python_worker/workflow/context.py`：

```python
def build_planner_context(state, scope, role, prompt, memories=None, attempts=None) -> PlannerContext
def build_reflector_context(plan, results, before, after) -> ReflectorContext
def build_text_refine_context(original, instruction, style_hint=None) -> list[ChatMessage]
def build_merge_planner_context(base, branches, prompt) -> MergePlannerContext
def build_failure_feedback(plan, failures, diff=None, reflection=None) -> FailureFeedback
```

所有构造器：
- **纯函数**：相同输入相同输出
- **可测**：每个 builder 有 golden snapshot 测试
- **可观测**：返回前打 debug log（tokens 估算 / 实际字段数）

---

## 11. 上下文调优工具（Phase 2）

```bash
# CLI 工具
python -m forgeppt.tools.ctx_inspect \
    --workflow_id=wf-123 \
    --node_id=agent-2 \
    --output planner_ctx.json
```

把实际生成的 context 落盘，方便 prompt 调优。

---

## 12. 反模式（绝对不做）

- ❌ 把整个 PPTState JSON 塞进 prompt
- ❌ 在 Tier 1 提供「全部 textbox 原文」让 Planner 直接改文字
- ❌ 在 retry 时累积所有历史 plan（只保留最近一次失败）
- ❌ 在 system prompt 里硬编码工具能力（必须从 ToolManifest 生成）

---

## 13. 测试要求

- **Token 估算单测**：构造 50 页 deck，断言 Tier 1 token < 2200。
- **降级单测**：当 deck 极大时，sample_chars 自动降到下限。
- **Diff 单测**：相同 state diff 为空；改一个 textbox 颜色 diff 精准。
- **Builder 快照**：每个 builder 有 1 个 golden output。

---

## 14. Phasing

| 阶段 | 范围 |
|---|---|
| **MVP** | Tier 1（含 sample_text）+ Tier 2（仅 Solver 内部） + Tier 3（含 failures） |
| Phase 2 | + Memory 注入；+ Plan 缓存；+ StateDiffDigest 给 Reflector |
| Phase 3 | + 视觉摘要（slide 渲染缩略图给 multi-modal LLM） |
| Future | 自适应预算：根据历史成功率自动调 sample_chars |

---

## 15. 待决策

1. **`sample_text` 默认开启还是关闭？** 倾向**开启**，因为成本可控。
2. **Tier 1 是否包含 image_count / dominant_colors？** 倾向**包含**，对主题类决策有帮助。
3. **Memory 注入位置**：system prompt 内 vs user prompt 后？倾向 system prompt 内，作为「背景知识」。
4. **缓存命中率目标**：Phase 2 上线后争取 30%+。需要先采样 baseline。
