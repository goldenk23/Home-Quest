# Python AI Floor-Plan Integration — Beginner Guide

This guide explains only the AI feature inside the Python/Tkinter editor shown in the screenshots. The old React `Thinker.tsx` and Node `server/` path is not part of this working integration.

## 1. The whole flow in one picture

```text
User types a house request
        ↓
generate_layout/tab.py reads the prompt
        ↓
ai_client.py sends prompt + rules to Vertex AI Gemini
        ↓
Gemini returns native VastuCraft JSON
        ↓
ai_validator.py checks that JSON
        ↓
Invalid? ai_client.py asks Gemini to repair it (up to 3 attempts)
        ↓
Valid? tab.py passes it to LayoutSerializer.load_document(...)
        ↓
layout_serializer.py backs up the old plan and creates canvas objects
        ↓
Existing 2D canvas and embedded 3D viewer refresh
```

Think of this as a restaurant:
- `tab.py` is the waiter taking the order.
- `ai_client.py` carries the order to Gemini.
- `architecture_rules.md` is the recipe book.
- `ai_validator.py` is quality control.
- `layout_serializer.py` plates the accepted result on the canvas.

## 2. Read these files in this order

1. `2D_layout/2dlayoutMaker-main/toolbar.py`, around line 672 — creates `GenerateLayoutTab`.
2. `2D_layout/2dlayoutMaker-main/generate_layout/tab.py`, lines 50–72 and 78–80 — imports the AI client and stores UI/chat state.
3. The same `tab.py`, lines 476–660 — builds the AI card, starts generation, receives the result, and loads it.
4. `2D_layout/2dlayoutMaker-main/generate_layout/ai_client.py`, lines 1–220 — complete Gemini request and repair loop.
5. `2D_layout/2dlayoutMaker-main/generate_layout/architecture_rules.md` — exact instructions sent to Gemini.
6. `2D_layout/2dlayoutMaker-main/generate_layout/ai_validator.py`, starting at line 121 — strict safety/geometry validation.
7. `2D_layout/2dlayoutMaker-main/layout_serializer.py`, lines 1374–1398, then 380 onward — safely replaces state and draws the JSON.
8. `2D_layout/2dlayoutMaker-main/app.pyw`, around lines 230–263 and 421–446 — connects serializer, toolbar, autosave, and 3D refresh.

## 3. Step 1: the app creates the AI tab

Open `toolbar.py` near line 672:

```python
GenerateLayoutTab(model=model, tools=tools, view=view, actions=actions).build(gen_layout_body)
```

This creates the Generate Layout screen and gives it references to the existing editor. Most importantly, `actions` later provides `actions.serializer`, so AI output can use the normal document-loading path instead of inventing a second renderer.

In `generate_layout/tab.py` near line 51:

```python
from .ai_client import generate_layout as ai_generate_layout, AIConfigError, AIGenerationError
```

This imports the provider function and the two expected error types.

## 4. Step 2: the UI collects the prompt

Read `generate_layout/tab.py` in this order:

### `_build_ai_section`, line 476
Creates the prompt textbox, Generate button, New Design button, and status label. The Generate button calls `_on_ai_generate`.

### `_on_ai_reset`, line 562
Clears two pieces of conversational state:

```python
self._ai_messages = []
self._ai_previous_layout = None
```

That is why **New design** starts a completely separate conversation.

### `_on_ai_generate`, line 569
This function:
1. Stops duplicate clicks while a request is running.
2. Reads and checks the textbox.
3. Adds the new user message to `_ai_messages`.
4. Copies the previous validated layout for refinement.
5. Disables the button and changes it to `Working…`.
6. Starts a background thread.

The important call is near line 596:

```python
result = ai_generate_layout(messages, previous)
```

A background thread is essential because an internet request may take seconds. Calling Gemini directly on Tkinter’s main thread would freeze buttons, scrolling, and window painting.

The worker cannot safely edit Tkinter widgets. It therefore puts either `("ok", result)` or `("err", error)` into `_ai_queue`.

### `_poll_ai_queue`, line 612
Tkinter checks the queue every 150 ms using `widget.after(...)`. On success it runs:

```python
applied = self._actions.serializer.load_document(layout, confirm=True)
```

Only a fully generated and validated layout reaches this line. If applying succeeds, the validated layout and assistant summary are saved as conversation history. A later prompt is therefore a refinement, not an unrelated request.

## 5. Step 3: configuration and authentication

Open `generate_layout/ai_client.py`.

### `_load_repo_env`, lines 34–63
Reads the repository-root `.env` without overwriting environment variables already supplied by Windows.

### `_config`, line 65
Reads:
- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_CLOUD_LOCATION`
- `AI_MODEL`
- `AI_MAX_TOKENS`

It defaults to Vertex AI Gemini 2.5 Pro and limits output to at most 32,000 tokens.

Authentication does **not** place a Google password or API key in source code. It uses Google Application Default Credentials (ADC):

```powershell
gcloud auth application-default login
```

The SDK uses those local credentials here:

```python
client = genai.Client(vertexai=True, project=project, location=location)
```

Required Python package in the editor virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install google-genai==2.14.0
```

Do not commit `.env` credentials or ADC files.

## 6. Step 4: giving Gemini the rules

`ai_client.py::_rules`, line 80, reads:

`generate_layout/architecture_rules.md`

That Markdown file is the most important prompt-engineering file. It tells Gemini:
- Output one native VastuCraft JSON document.
- Use canvas pixels with Y increasing downward.
- Use `20 pixels = 1 foot`.
- Include required metadata, rooms, shapes, furniture, text, and compass.
- Create wall gaps that match doors and windows.
- Use only supported furniture and flooring names.
- Return a complete document during refinement, not a small patch.

The user’s text says *what home they want*. `architecture_rules.md` says *how that home must be represented for this editor*.

When refining, `generate_layout` also adds the last validated layout to the system instructions. Gemini is told to preserve everything the latest user message did not ask to change.

## 7. Step 5: calling Gemini and repairing mistakes

Read `ai_client.py::generate_layout`, starting at line 100.

The expected Gemini response is an envelope:

```json
{
  "layout": { "version": "1.0", "metadata": {}, "rooms": [] },
  "assistantMessage": "Short explanation of the design"
}
```

Important request settings:

```python
response_mime_type="application/json"
temperature=0.2
thinking_config=types.ThinkingConfig(thinking_budget=2048)
```

- JSON mode makes non-JSON output less likely.
- Low temperature makes output more consistent.
- A bounded thinking budget leaves enough output space for the large layout JSON.

`_extract_json`, line 87, parses the response. It also tolerates an accidental Markdown JSON fence.

Then the client runs:

```python
errors = validate_layout(layout)
```

If there are no errors and `assistantMessage` is valid, the function returns the result. Otherwise, it adds the failed response and clear error feedback to the conversation and asks Gemini for a complete corrected document. `_MAX_ATTEMPTS = 3` prevents an endless loop.

Retries can use up to the existing 32,000-token ceiling. If Vertex reports `MAX_TOKENS`, the client explains that the response was truncated and asks for a smaller complete result instead of accepting partial JSON.

Provider/configuration failures become `AIConfigError`. Network, malformed-output, and exhausted-repair failures become `AIGenerationError`. `tab.py` catches both and displays the message in the status label.

## 8. Step 6: strict validation

Open `generate_layout/ai_validator.py::validate_layout`, line 121.

Never trust AI output merely because it is valid JSON. JSON can be syntactically correct and still describe an impossible plan. The validator checks, among other things:
- Root object and native version.
- Required metadata and the `20 px = 1 ft` contract.
- Canvas bounds and finite numbers.
- Room dimensions and room overlap.
- Required arrays such as rooms, furniture, shapes, and text.
- Supported flooring and furniture names.
- Wall-erased intervals.
- Doors being close to matching wall gaps.
- Furniture remaining inside valid bounds.
- Compass direction.

It returns a list:

```python
[]                         # valid
["rooms[1] overlaps..."]  # invalid
```

Returning errors instead of immediately crashing is useful because all problems can be sent to Gemini in one repair request.

At the bottom of `ai_validator.py` is a small assert-based self-check. Run it with:

```powershell
.\.venv\Scripts\python.exe generate_layout\ai_validator.py
```

## 9. Step 7: safely applying the result

The AI does not draw canvas items itself. This is a key design decision.

`app.pyw` creates the existing serializer around line 231:

```python
self.serializer = LayoutSerializer(self.model, self.view, self.tools, self.actions)
```

`layout_serializer.py`, around line 57, exposes that same object as:

```python
self.actions.serializer = self
```

That is how `GenerateLayoutTab` reaches it through `self._actions.serializer`.

Read `layout_serializer.py::load_document`, line 1374. It:
1. Validates the complete document before changing current state.
2. Asks permission before replacing an existing drawing.
3. Writes a backup of the current plan.
4. Saves previous project and canvas state for rollback.
5. Replaces project state.
6. Materializes the active floor.
7. Restores the previous state if drawing fails.
8. Clears stale undo/redo entries.
9. Sends a post-mutation notification.

This is a transaction-like pattern: either the new plan loads completely, or the editor tries to restore the old plan.

## 10. Step 8: converting JSON into canvas objects

Read `layout_serializer.py::deserialize_layout`, starting at line 380.

It clears old non-grid canvas items and recreates data in a safe visual order:
1. Shapes and background polygons.
2. Rooms and walls.
3. Furniture.
4. Semantic or inferred windows.
5. Text labels.
6. Compass state.

Finally it resets temporary drawing modes so normal editing can continue.

Notice the separation of responsibilities:
- Gemini **describes** the plan as JSON.
- The validator **approves or rejects** it.
- The serializer **turns approved data into existing editor objects**.

This is why no `.hq.json` converter and no second AI renderer are needed.

## 11. Step 9: autosave and embedded 3D refresh

After a successful load, `LayoutSerializer.load_document` calls `actions.notify_post_mutation()`.

In `app.pyw`, around line 261:

```python
self.actions.post_mutation_callback = self._on_project_mutation
```

Read `_on_project_mutation`, starting around line 421. It refreshes parity controls, schedules local autosave, and schedules the existing embedded viewer refresh. The 3D viewer therefore receives the same accepted document used by the 2D editor; AI does not talk directly to 3D.

## 12. How conversational refinement works

Suppose the first prompt is:

```text
Create a north-facing three-bedroom home.
```

After success, `tab.py` stores:
- The user message in `_ai_messages`.
- Gemini’s summary as an assistant message.
- The validated JSON in `_ai_previous_layout`.

A second prompt can say:

```text
Keep everything else, enlarge the kitchen and add a study window.
```

`ai_client.py` sends both the chat history and the complete previous layout. Gemini must return another **complete** document. That new document goes through the same validation and serializer pipeline.

Pressing **New design** clears this state. It does not erase the canvas by itself; it only starts a fresh AI conversation.

## 13. Why there are two validation gates

You will see validation in both the AI layer and serializer layer. This is intentional:

1. `ai_validator.py` gives AI-specific, detailed repair feedback before anything touches editor state.
2. `layout_serializer.py::load_document` protects the application boundary and validates every caller, including normal file loading.

Analogy: airport security checks your documents before boarding, and the destination checks entry rules again. Different entry paths remain safe.

## 14. Run and test it

From `2D_layout/2dlayoutMaker-main`:

```powershell
# Syntax check
.\.venv\Scripts\python.exe -m py_compile generate_layout\tab.py generate_layout\ai_client.py generate_layout\ai_validator.py

# Validator self-check
.\.venv\Scripts\python.exe generate_layout\ai_validator.py

# Real provider check (uses Vertex and may incur usage cost)
.\.venv\Scripts\python.exe -c "from generate_layout.ai_client import generate_layout; r=generate_layout([{'role':'user','content':'small north-facing two-bedroom home'}]); print(r['attempts'], len(r['layout']['rooms']))"

# Launch only the Python editor directly
.\.venv\Scripts\python.exe app.pyw
```

The current `2D_layout/01_run.txt` launches the repository wrapper `run-home-quest.ps1`; that wrapper belongs to the older combined launch path. For learning and debugging this Python feature, the direct `app.pyw` command is clearer.

## 15. Debugging map

| Symptom | First file/function to inspect |
|---|---|
| Generate button does nothing | `tab.py::_on_ai_generate` |
| UI remains on Working | `tab.py::worker`, `_schedule_ai_poll`, `_poll_ai_queue` |
| Credentials/project error | `ai_client.py::_config` and `genai.Client(...)` |
| Invalid or truncated JSON | `ai_client.py::_extract_json` and repair loop |
| Geometry/room/furniture rejection | `ai_validator.py::validate_layout` |
| Valid result does not appear | `tab.py::_poll_ai_queue` and `layout_serializer.py::load_document` |
| Old plan is lost or replacement fails | `load_document` backup/rollback path |
| 2D updates but 3D does not | `app.pyw::_on_project_mutation` and `_schedule_viewer_refresh` |

When debugging, print or log only safe metadata such as attempt number, error list, room count, and Vertex finish reason. Do not print credentials.

## 16. The five ideas to remember

1. Keep the network request off the Tkinter UI thread.
2. Treat every AI response as untrusted input.
3. Ask for structured JSON, then validate its meaning—not only its syntax.
4. Repair invalid output a limited number of times.
5. Feed accepted data into the existing serializer and renderer instead of building duplicate systems.

If you understand `tab.py → ai_client.py → ai_validator.py → layout_serializer.py`, you understand the complete AI integration.