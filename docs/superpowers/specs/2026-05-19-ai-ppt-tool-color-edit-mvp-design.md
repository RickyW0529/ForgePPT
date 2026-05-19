# AI PPT Tool-Calling Color Edit MVP Design

## Goal

Enable the MVP flow where a user uploads a PPTX, gives a natural-language instruction such as "把第三页整体颜色改成蓝色", the AI selects and calls a PPT editing tool, the tool updates the current `PPTState`, the exporter writes those changes back into a PPTX, and the user can download the modified file.

This design prioritizes proving the end-to-end tool-calling workflow. The first concrete tool only supports text styling, while the protocol leaves room for future tools such as background color, shape fill, image replacement, and multi-step editing.

## Scope

In scope:

- Add an AI-visible PPT editing tool contract for applying text style changes.
- Route theme/style requests through AI tool calling instead of only structured output.
- Execute returned tool calls against `PPTState` in the backend.
- Write text color/style changes back into exported PPTX files.
- Add tests for tool-call execution and PPTX color write-back.

Out of scope for this MVP:

- Full agent loop with multiple reasoning rounds.
- Background color or shape fill editing.
- Precise per-element semantic targeting beyond slide number and all text.
- Async task persistence or download storage redesign.
- Frontend UI changes beyond sending existing `theme` edit requests, unless already missing.

## Architecture

The MVP keeps the current workflow shape:

```text
/tasks
  -> build_graph()
  -> editor_node
  -> AI chooses tool call
  -> backend executes tool call against PPTState
  -> exporter_node
  -> recompose_pptx
  -> response.export_path
  -> download endpoint
```

`EditRequest.type == "theme"` remains the entry point for user color/style instructions. Instead of asking the model to directly produce `ThemeOutput`, the theme path presents an editing tool schema to the model and requires at least one tool call.

## Tool Protocol

Add an AI-visible tool named `ppt_apply_style`.

Initial input model:

```python
class PPTApplyStyleInput(BaseModel):
    slide_number: int | None
    target: Literal["all_text"]
    font_color: str | None
    font_size_multiplier: float | None
    bold: bool | None
```

Semantics:

- `slide_number`: one-based slide number. `None` means all slides.
- `target`: currently only `"all_text"`, meaning all text boxes in the selected slide scope.
- `font_color`: optional `#RRGGBB` text color.
- `font_size_multiplier`: optional multiplier for existing text sizes.
- `bold`: optional bold setting.

For the user prompt "把第三页整体颜色改成蓝色", the expected tool call is equivalent to:

```json
{
  "slide_number": 3,
  "target": "all_text",
  "font_color": "#0000FF",
  "font_size_multiplier": null,
  "bold": null
}
```

The tool execution result should report how many text boxes were updated and which slide scope was used.

## Execution Design

The current registry tools are stateless callables. PPT editing tools need access to mutable `PPTState`, so the MVP should separate:

- **AI-visible schema**: LangChain structured tool definition shown to the LLM.
- **Backend executor**: local Python function that applies validated tool arguments to `PPTState`.

The theme node flow:

1. Build a PPT editing agent prompt containing current slide count and the user's instruction.
2. Bind `ppt_apply_style` to the LLM.
3. Invoke the model.
4. Read `response.tool_calls`.
5. If no PPT editing tool was called, return a failed `EditResult`.
6. Validate each tool call input.
7. Apply each supported tool call to a copied `PPTState`.
8. Return updated `ppt_state` plus completed `EditResult` summary.

The node should fail clearly for unsupported tool names, invalid slide numbers, invalid colors, or missing actionable style fields.

## PPTX Write-Back

`recompose_pptx` currently updates text content but preserves formatting without applying modified `TextBox.style` fields. The MVP must apply supported style fields to each text shape's runs:

- `font_color` -> `run.font.color.rgb = RGBColor.from_string(hex_without_hash)`
- `font_size_pt` -> `run.font.size = Pt(value)`
- `bold` -> `run.font.bold`
- `italic` -> `run.font.italic`

If a style field is `None`, the recomposer leaves the original formatting unchanged. If a shape has no runs, it creates a run for the text and applies available style fields.

## Error Handling

- No tool call from the model: failed edit result with a message that the AI did not call a PPT editing tool.
- Unsupported tool name: failed edit result naming the unsupported tool.
- Invalid slide number: failed edit result.
- Tool call validates but matches no text boxes: completed or failed should be explicit; MVP should treat this as failed because no visible edit occurred.
- Export errors continue through the existing exporter error path.

## Testing

Add tests for:

1. Theme node executes a mocked `ppt_apply_style` tool call and updates only the requested slide's text colors.
2. Theme node returns failed edit result when the mocked LLM response has no tool calls.
3. `recompose_pptx` writes `TextBox.style.font_color` into the output PPTX and `parse_pptx` can read it back.

Existing refine and placeholder behavior should continue to pass.

## Future Extensions

After this MVP, add more tools rather than overloading `ppt_apply_style`:

- `ppt_set_background`
- `ppt_apply_shape_style`
- `ppt_replace_image`
- `ppt_insert_svg`
- `ppt_select_elements`

A later full agent loop can allow the model to inspect screenshots, plan multi-step edits, call multiple tools, and verify results.
