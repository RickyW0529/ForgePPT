# 04 - Prompt Templates

**Files:**
- Create: `python_worker/llm/prompts.py`
- Create: `python_worker/tests/test_prompts.py`

---

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_prompts.py
from llm.prompts import build_refiner_messages, build_svg_messages


def test_refiner_messages_structure():
    """Refiner messages should be a list of System + Human messages."""
    messages = build_refiner_messages("Original text", "Make it shorter")
    assert len(messages) == 2
    assert messages[0].type == "system"
    assert "PPT文案编辑" in messages[0].content or "editor" in messages[0].content.lower()
    assert messages[1].type == "human"
    assert "Original text" in messages[1].content
    assert "Make it shorter" in messages[1].content


def test_svg_messages_structure():
    """SVG messages should be a list of System + Human messages."""
    messages = build_svg_messages("Blue tech icon", "minimalist")
    assert len(messages) == 2
    assert messages[0].type == "system"
    assert "SVG" in messages[0].content or "svg" in messages[0].content
    assert messages[1].type == "human"
    assert "Blue tech icon" in messages[1].content


def test_refiner_with_preferences():
    """Refiner should inject memory preferences into system prompt."""
    prefs = "Prefer concise, bullet-style text."
    messages = build_refiner_messages("Text", "Shorten", memory_preferences=prefs)
    assert prefs in messages[0].content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_prompts.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'llm.prompts'"

- [ ] **Step 3: Write minimal implementation**

```python
# python_worker/llm/prompts.py
from langchain_core.messages import HumanMessage, SystemMessage


REFINER_SYSTEM_TEMPLATE = """You are a professional PPT copy editor. Your task is to rewrite PPT text according to user instructions.

Output requirements:
- Preserve the core information of the original text, adjust style and wording according to user instructions
- Output language must match the original text
- Strictly follow the specified JSON format output
{memory_preferences}"""


SVG_SYSTEM_TEMPLATE = """You are an expert SVG graphic designer. Generate self-contained SVG 1.1 code based on the user's description.

Technical constraints:
- Generate self-contained SVG 1.1 code
- Use only inline CSS styles (no external stylesheets)
- No external resource references (images, fonts, etc.)
- Ensure valid XML structure with proper xmlns declaration
{memory_preferences}"""


def build_refiner_messages(
    original_text: str,
    instruction: str,
    memory_preferences: str = "",
) -> list[SystemMessage | HumanMessage]:
    """Build message list for text refinement."""
    system_content = REFINER_SYSTEM_TEMPLATE.format(
        memory_preferences=memory_preferences,
    )
    human_content = f"""Original text:
{original_text}

Instruction:
{instruction}"""
    return [
        SystemMessage(content=system_content),
        HumanMessage(content=human_content),
    ]


def build_svg_messages(
    description: str,
    style_hint: str | None = None,
    memory_preferences: str = "",
) -> list[SystemMessage | HumanMessage]:
    """Build message list for SVG placeholder generation."""
    system_content = SVG_SYSTEM_TEMPLATE.format(
        memory_preferences=memory_preferences,
    )
    style_section = f"\nStyle preference: {style_hint}" if style_hint else ""
    human_content = f"""Description:
{description}{style_section}

Generate the SVG code:"""
    return [
        SystemMessage(content=system_content),
        HumanMessage(content=human_content),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_prompts.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add python_worker/llm/prompts.py python_worker/tests/test_prompts.py
git commit -m "feat: add prompt templates for text refinement and SVG generation"
```
