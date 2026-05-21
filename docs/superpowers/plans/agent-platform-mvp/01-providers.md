
# Module 1 · Provider Management

> 对齐 spec `03-llm-provider-management.md`。目标：替换 `python_worker/llm/client.py` 工厂为统一 Router。

## Sub-steps

### 1.1 Models + Adapter Protocol（先写测试）

**Files to create:**
- `python_worker/agent_platform/__init__.py`
- `python_worker/agent_platform/providers/__init__.py`
- `python_worker/agent_platform/providers/models.py`
- `python_worker/agent_platform/providers/adapters/__init__.py`
- `python_worker/agent_platform/providers/adapters/base.py`
- `python_worker/tests/agent_platform/__init__.py`
- `python_worker/tests/agent_platform/providers/__init__.py`
- `python_worker/tests/agent_platform/providers/test_models.py`

**Tests:**
- `LLMRequest` schema validation
- `LLMResponse` 含 token / cost / latency 字段
- `TokenUsage.total` 计算
- `RequestMetadata.purpose` 枚举校验

**Verification:**
```bash
cd python_worker && pytest tests/agent_platform/providers/test_models.py -v
```

---

### 1.2 OpenAI + DeepSeek Adapters

**Files:**
- `python_worker/agent_platform/providers/adapters/openai_adapter.py`
- `python_worker/agent_platform/providers/adapters/deepseek_adapter.py`
- `python_worker/tests/agent_platform/providers/test_openai_adapter.py`
- `python_worker/tests/agent_platform/providers/test_deepseek_adapter.py`

**Tests:**
- mock OpenAI SDK：验证 request 构造、response 规范化、token / cost 计算
- structured output：`response_format=JSONSchema` 传参正确
- DeepSeek 走 OpenAI 兼容协议，断言 base_url 不同

**Verification:**
```bash
cd python_worker && pytest tests/agent_platform/providers/test_*_adapter.py -v
```

---

### 1.3 Registry + Router + Budget

**Files:**
- `python_worker/agent_platform/providers/registry.py`
- `python_worker/agent_platform/providers/router.py`
- `python_worker/agent_platform/providers/budget.py`
- `python_worker/tests/agent_platform/providers/test_registry.py`
- `python_worker/tests/agent_platform/providers/test_router.py`
- `python_worker/tests/agent_platform/providers/test_budget.py`

**Tests:**
- Router：primary 成功直接返回
- Router：primary 失败 → fallback；fallback 也失败 → AllProvidersExhausted
- Router：budget 不够时降级到 cheap
- Budget：reserve / commit / over-limit
- Registry：注册查询

**Verification:**
```bash
cd python_worker && pytest tests/agent_platform/providers/ -v
```

---

### 1.4 Config Loader + 整合现有 callers

**Files:**
- `python_worker/agent_platform/providers/config.py`
- `python_worker/config/providers.yaml`（新）
- `python_worker/tests/agent_platform/providers/test_config.py`

**Migration:**
- 现有 `python_worker/llm/client.py` 暂保留（向后兼容），但加一个 `get_router()` 入口。
- 旧的 `get_llm_client()` 内部转调 Router，保证现有代码不报错。Phase 2 再彻底删除旧文件。

**Tests:**
- YAML 加载 + env 替换
- 缺主 provider key 时 fail-fast
- 缺 fallback key 时仅警告

**Verification:**
```bash
cd python_worker && pytest tests/agent_platform/providers/ -v
cd python_worker && python -c "from agent_platform.providers import get_router; print(get_router())"
```

---

## Definition of Done

- 4 个 sub-step 测试全绿
- `mypy python_worker/agent_platform/providers` 无 error
- 新 Router 能成功调一次真实 OpenAI（需 `PPT_OPENAI_API_KEY`），smoke 脚本：
  ```bash
  cd python_worker && python -m agent_platform.providers.smoke
  ```
- 提交：`feat(providers): introduce ProviderRouter with multi-adapter and fallback`

## Deviations

（执行时若与 spec 03 有偏离，在此记录）
