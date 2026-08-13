# AI Layout Generator — Simple File and Function Guide

This guide explains what happens behind the scenes when someone uses the AI Layout Generator.

It is written for everyone. You do not need to know AI, architecture, or this codebase before reading it.

For a shorter overview of the feature, read [AI layout generation](../../../docs/ai-layout-generation.md).

## The one idea to remember

**The AI does not draw the house.**

The AI reads the user's request and returns an organized list of what the user wants. For example:

- three bedrooms;
- a kitchen in the south-east;
- a prayer room in the north-east;
- an east-facing entrance; and
- a 40 × 60 ft plot.

Normal Python code then turns that list into real room boxes, walls, doors, windows, and furniture.

Before anything appears on the screen, more Python code checks the plan. If the plan is bad, it is rejected. The user's current drawing is not replaced.

```text
User writes a request
        ↓
The AI understands the request
        ↓
Python code places the rooms
        ↓
Python code adds walls, doors, windows, and furniture
        ↓
Python code checks the complete plan
        ↓
The app makes a backup of the old plan
        ↓
The checked plan is shown on the canvas
```

## A few simple words used in this guide

Some function and file names use technical words. Here is what those words mean:

- **JSON** — text arranged in a fixed structure so the program can read it.
- **DesignSpec** — a clean list of what the user asked for. Think of it as the house wish list.
- **Layout** — the finished drawing data: room positions, walls, doors, furniture, and labels.
- **Native v1** — the app's format for one floor.
- **Native v2** — the app's full project format. It can hold several floors.
- **Planner** — Python code that decides where each room should go.
- **Candidate** — one possible room arrangement made by a planner.
- **Validator** — a checker. It returns a list of problems. An empty list means the plan passed.
- **Serializer** — the part that loads saved plan data and rebuilds the visible canvas.
## The complete journey of one request

### Step 1: The app creates the AI screen

When the 2D editor starts, `app.pyw` creates the canvas, drawing tools, action history, and layout loader.

It then calls `toolbar.py`. That file creates the **Generate Layout** tab.

The main chain is:

```text
app.pyw
  → toolbar.setup_toolbar()
  → GenerateLayoutTab(...)
  → GenerateLayoutTab.build()
```

`top_action_toolbar.py` contains the button that opens this tab. It only changes the visible tab. It does not call the AI.

### Step 2: The user clicks “Generate with AI”

The click calls:

```text
GenerateLayoutTab._on_ai_generate()
```

This function first checks simple things:

- Is the request empty?
- Is another request already running?
- Is the layout loader available?

If everything is ready, it:

1. saves the user's message in the chat list;
2. remembers the last accepted plan, if there is one;
3. remembers the last accepted house wish list, if there is one;
4. creates a cancel signal;
5. gives this request a new number; and
6. starts the AI work away from the main screen.

The AI work runs separately so the app does not freeze. It does not touch the canvas directly.

### Step 3: `ai_client.py` does the main work

The separate work calls:

```text
generate_layout.ai_client.generate_layout()
```

This is the main function behind the AI feature.

It reads the settings, connects to Gemini, checks whether the app should use `comb` or `multi`, and watches the time, call limit, and cancel signal.

It sends progress messages back to the AI tab. These messages appear in the **Backend Activity** box.

### Step 4: The app chooses how to place rooms

There are two choices.

#### `comb` mode

The AI returns a small room list. The list says things such as:

- which rooms are needed;
- whether a room belongs in the north, south, east, or west;
- whether it needs a window;
- which rooms need a connecting door; and
- whether it belongs above or below the middle hallway.

Then `layout_engine.build_layout()` makes the exact room boxes.

This mode uses one long hallway across the middle. Rooms sit above and below it.

#### `multi` mode

The AI returns a `DesignSpec`, which is the cleaned house wish list.

Python code then:

1. checks that the wish list matches the user's words;
2. checks whether all rooms can fit on the plot;
3. asks several local planners to make possible arrangements;
4. rejects arrangements that break important rules;
5. gives each valid arrangement a score; and
6. chooses the best arrangement that is different from the others.

The AI does not choose the final room coordinates in this mode. Python planners do that.

### Step 5: Furniture is added separately

After the room shell is valid, the AI gets another smaller job: suggest furniture for the fixed rooms.

The room positions are not open for change during this step.

The AI may only use furniture names that the app supports. Python code joins the suggested furniture with the already-checked room shell.

### Step 6: Small mechanical problems are fixed

`geometry_autofix.autofix_layout()` fixes small and clear problems, such as:

- a wall opening going slightly past a corner;
- two matching rooms not having the same opening on their shared wall;
- a door sitting near, but not on, its wall opening; or
- furniture sitting slightly outside its room.

This function is not allowed to approve the plan. It only tries small fixes. The plan must still pass the checker afterwards.

### Step 7: The full plan is checked

`ai_validator.validate_layout()` checks the drawing data.

`ai_validator.validate_design()` checks whether the drawing behaves like a usable house and follows the important parts of the request.

If either function returns problems, the plan is not accepted.

Some problems may be sent back to the AI for a small number of repair attempts. There is always a fixed call and time limit.

### Step 8: The result returns to the main screen

The separate AI work puts the result into a small message inbox called `_ai_queue`.

The main screen checks that inbox through:

```text
GenerateLayoutTab._poll_ai_queue()
```

Only this function may apply the result to the canvas.

Every request has a number. If an old or cancelled request finishes late, its number no longer matches. The result is ignored.

### Step 9: The old plan is backed up

Before replacing the current project, the AI tab writes a file named like:

```text
before_ai_apply_20260809_123456.json
```

If this backup cannot be written, the new AI plan is not applied.

### Step 10: The checked plan is loaded

The AI tab calls:

```text
LayoutSerializer.load_document()
```

This function checks the project format again, replaces the project data, and redraws the canvas.

If anything fails while loading or drawing, it restores the old project and old canvas.

After success, the app runs its normal update work. This includes autosave, room detection, floor controls, and 3D-view refresh.

## What happens when the user asks for a change?

### Change in `comb` mode

The old complete plan is sent as part of the request. The AI returns a complete changed plan.

The result still goes through small fixes and all checks before it can replace the canvas.

### Change in `multi` mode

The AI first puts the new message into one of three groups:

- **answer** — the user asked a question, so reply without changing the plan;
- **small edit** — change paint, flooring, one door, or one window without moving rooms; or
- **room change** — add, remove, rename, resize, or move a room, so plan the rooms again.

For a small edit, `_surgical_diff_errors()` compares the old and new room boxes. It rejects the edit if any room was secretly added, removed, moved, or resized.

For a room change, the accepted `DesignSpec` is updated and the planners run again.

## What happens for several floors?

Several floors are supported only in `multi` mode.

`_detect_floor_count()` understands common words such as:

- `duplex`;
- `triplex`;
- `G+1`;
- `3 floors`; and
- `two-storey`.

At most four floors are made.

The flow is:

```text
_detect_floor_count()
  → _allocate_floors()
  → generate_layout() once for each floor
  → native_v2.build_multi_floor_document()
```

`_allocate_floors()` decides which requested rooms belong on each floor. Each floor then goes through the normal one-floor process.

Finally, `native_v2.py` puts all floors into one project.

**Important limit:** each floor is planned separately. The code does not make sure that stairs line up from one floor to the next. The user must check and fix that by hand.

# Main files inside `generate_layout`

## `tab.py` — the screen and safe hand-off

### What this file does

This file owns the AI part of the Generate Layout tab.

It shows the request box, chat messages, buttons, progress, activity messages, results, and floor buttons.

It also keeps slow AI work away from the main screen and makes sure only the newest successful result can be loaded.

### Important class

#### `GenerateLayoutTab`

This class remembers:

- the chat messages;
- whether AI work is running;
- the current cancel signal;
- the current request number;
- the last accepted plan;
- the last accepted `DesignSpec`;
- progress messages waiting for the screen; and
- the active floor.

### Important functions

#### `build()` and `_build_ai_section()`

Create the visible controls.

**Called by:** `toolbar.setup_toolbar()`.

#### `_on_ai_generate()`

Starts a new request.

**Calls:** `ai_client.generate_layout()` in separate work.

**Uses:** chat messages, previous plan, previous `DesignSpec`, cancel signal, and a function that sends progress messages back to the screen.

#### `_poll_ai_queue()`

Reads progress and final results on the main screen.

**Calls:** `LayoutSerializer.load_document()` after writing a backup.

**Also does:** ignores old results, shows errors, restores failed prompts, saves accepted chat/spec state, and shows floor buttons.

#### `_on_ai_cancel()`

Marks the current request as cancelled.

The Google request may already be running, so this function may not stop billing immediately. It does make sure the returned plan is not applied.

#### `_on_ai_reset()`

Starts a completely new design.

**Calls:** `LayoutSerializer.load_document(new_project())`.

It also clears the AI chat, old plan, old `DesignSpec`, and floor buttons.

#### `_on_switch_floor()`

Shows a selected floor on the canvas.

**Calls:** `LayoutSerializer.activate_floor()`.

### This file depends on

- `ai_client.py` for AI work;
- `design_spec.py` for the accepted wish list;
- `layout_serializer.py` for loading and backups; and
- Tkinter/CustomTkinter for the screen.

It does not calculate room positions.

## `ai_client.py` — the main AI controller

### What this file does

This is the centre of the AI process. It connects all AI and planning steps.

It decides:

- which model and settings to use;
- which planner mode to use;
- how many AI calls are allowed;
- when to stop for time or cancellation;
- how to read the AI's JSON;
- when to ask for a repair;
- how to handle follow-up messages; and
- when the final plan is safe to return.

### Most important function

#### `generate_layout()`

This is the main backend function.

**Called by:** `tab.py::_on_ai_generate()`.

**Receives:** chat messages, old plan, old `DesignSpec`, progress function, and cancel signal.

**Returns:** checked layout, reply message, call count, time taken, planner details, and sometimes a several-floor project.

**Calls:** almost every other file explained below.

### Other important functions

#### `_config()`

Reads model, Google project, token, and timeout settings. Number settings are kept inside safe minimum and maximum values.

#### `_planner_config()`

Reads `AI_LAYOUT_PLANNER` and the repeatable seed number.

It accepts only `comb` or `multi`. A spelling mistake causes a clear error.

#### `_rules()`

Reads `architecture_rules.md` for `comb` mode.

#### `_extract_json()`

Reads the AI answer as JSON. It can handle a Markdown code fence or a little extra text around the JSON.

#### `_run_pass()`

Runs this limited loop:

```text
ask AI
  → read JSON
  → fix small geometry problems
  → check the plan
  → if needed, send the problem list back for repair
```

It is used for full-plan `comb` changes and small `multi` edits.

#### `_run_multi_planner()`

Runs all local room planners for `multi` mode.

It checks the `DesignSpec`, checks available space, gathers possible plans, rejects bad ones, scores good ones, and returns the best different choices.

#### `_detect_floor_count()`

Reads the number of floors from the latest user message.

#### `_allocate_floors()`

Uses one AI call to split requested rooms across floors and read the shared plot size and facing direction.

#### `generate_multi_floor_layout()`

Makes each floor separately and joins them into one v2 project.

#### `_surgical_diff_errors()`

Checks that a small edit did not change room names or room boxes.

### Error classes

- `AIConfigError` — setup, model, sign-in, project, or setting problem.
- `AIGenerationError` — the complete process could not make a plan.
- `AIValidationError` — the allowed attempts still did not pass checking.
- `AICancelledError` — the user cancelled.
- `AITimeoutError` — the work took longer than the allowed time.

The Google client is closed whether the request succeeds or fails.
## `architecture_rules.md` — rules given to the AI in `comb` mode

### What this file does

This file tells Gemini exactly what kind of data the app accepts.

It explains:

- the one-floor file shape;
- how feet become canvas pixels;
- required room fields;
- wall openings;
- door and window rules;
- supported furniture;
- compass rules; and
- safety limits.

### Who reads it?

`ai_client._rules()` reads it when the selected mode is `comb`.

`multi` mode does not read this file. Its shorter instructions are written inside `ai_client.py` because each `multi` step has a different job.

`docs/prompt.txt` is not used by the running AI process.

## `design_spec.py` — the clean house wish list

### What this file does

This file changes the AI's answer into a safe and clear `DesignSpec`.

A `DesignSpec` describes what the user wants without saying where every wall pixel should go.

### Important data classes

#### `Room`

Stores one requested room. It includes the room's stable ID, name, type, zone, size wishes, window need, entrance flag, flooring, and importance.

#### `Relationship`

Stores how two rooms should relate. For example:

- share a door;
- sit next to each other;
- stay near each other;
- stay separate; or
- attach a bathroom to a bedroom.

It uses room IDs, not display names, so two rooms with similar names do not get confused.

#### `DesignSpec`

Holds the whole wish list: plot, floors, rooms, room relationships, furniture wishes, assumptions, and notes showing where requirements came from.

### Important functions

#### `classify_room()`

Turns names such as “Master Bedroom” or “Guest Bath” into simple types such as `bedroom` or `bathroom`.

#### `make_room()`

Creates a cleaned room and gives it a unique ID.

#### `from_dict()`

Reads an AI-made `DesignSpec` dictionary.

It checks list sizes, field types, room IDs, relationship IDs, and safe value limits.

#### `align_with_brief()`

Compares the `DesignSpec` with the user's real words.

The user's clear request wins over an AI guess. For example, if the user asked for three bedrooms but the AI added four, this function corrects the list.

It also removes optional rooms that the AI invented during a new request.

#### `validate_spec()`

Checks whether the cleaned wish list is complete and internally correct.

#### `to_dict()`

Changes the Python `DesignSpec` back into normal JSON-ready data.

#### `from_program()`

Changes an old `comb` room program into a `DesignSpec` without another AI call.

#### `DesignSpec.summary()`

Creates the short human-readable room summary shown in the activity box.

### Who calls this file?

- `ai_client.generate_layout()`;
- `ai_client._run_multi_planner()`; and
- `tab.py`, when it remembers the accepted wish list.

This file does not call Gemini and does not draw anything.

## `feasibility.py` — checks whether the request can fit

### What this file does

This file answers a basic question before planning:

> Can rooms of useful size fit on this plot?

This prevents the app from making tiny unusable bedrooms just to force every request into the available space.

### Important parts

#### `ROOM_STANDARDS`

Stores practical minimum sizes and normal target areas for bedrooms, bathrooms, kitchens, living rooms, and other spaces.

#### `standard_for()`

Finds the practical size rules for one room. If the user asked for a larger size, the user's size is also considered.

#### `buildable_envelope()`

Calculates usable plot width and depth after removing requested empty space around the building.

#### `analyze()`

Checks:

- total room area;
- space needed for walls and movement;
- whether rooms needing windows can reach outside walls;
- whether too many rooms are forced into one direction; and
- whether room connections look too demanding.

It returns a `FeasibilityReport` containing:

- whether the request can fit;
- hard reasons it cannot fit;
- warnings;
- assumptions; and
- possible ways to simplify the request.

### Who calls it?

`ai_client._run_multi_planner()` calls `analyze()` before running planners.

Planner files also use `standard_for()` and `buildable_envelope()`.

## `layout_engine.py` — builds the `comb` plan

### What this file does

This file turns the small AI room program into a complete one-floor layout.

The plan has one hallway across the middle. Rooms are placed in a row above it and a row below it.

### Important functions

#### `get_planner()`

Checks whether the mode name is `comb` or `multi`.

The older comb builder remains available as the safe basic builder.

#### `build_layout()`

Creates:

- exact room boxes;
- the middle hallway;
- matching wall openings;
- room doors;
- outside windows;
- the main entrance;
- room labels;
- project details; and
- the north arrow.

#### `_column_widths_ft()`

Shares the plot width between rooms so the row ends exactly at the plot edge.

#### `_snap_door_interval()`

Finds a safe place for an opening and keeps it away from wall corners.

#### `_add_gap()` and `_finalize_gaps()`

Add wall openings, put them in order, and join openings that overlap.

### Who calls it?

`ai_client.generate_layout()` calls it in `comb` mode.

It does not call the AI or the screen.

## `planner.py` — shared rules for all `multi` planners

### What this file does

This file gives every `multi` planner the same basic room and result shapes.

It also keeps a list of available planners.

### Important data classes

#### `PlacedRoom`

One room box measured in feet. It includes its position, size, type, zone, window need, and entrance information.

#### `PlannerContext`

The information given to a planner: `DesignSpec`, seed number, and facing direction.

#### `TopologyCandidate`

One possible set of placed room boxes. Here, “topology” simply means the way rooms are arranged.

#### `LayoutCandidate`

One possible finished plan plus its errors, score, notes, and short identity code.

### Important functions

#### `register()`

Adds a planner to the shared planner list.

#### `strategies()`

Returns the planner list.

#### `run_strategy()`

Runs one chosen planner.

#### `validate_topology()`

Checks one room arrangement before the full layout is built.

It checks:

- every requested room appears once;
- no unknown room was added;
- room sizes are usable;
- rooms stay inside the plot;
- important direction requests are followed;
- rooms needing outside windows touch the outside; and
- important room relationships are met.

### Who calls it?

`ai_client._run_multi_planner()`.

All files inside `planners/` use its data classes and `register()` function.

## `planners/__init__.py` — loads all planners

This small file imports the planner files.

Importing them causes their `register()` lines to run. After that, `planner.strategies()` can see them.

**Called by:** `ai_client._run_multi_planner()`.

## `planners/comb.py` — keeps the old comb name available

This file registers the name `comb` in the shared planner list.

The real comb plan is already built directly by `layout_engine.build_layout()`, so `comb_strategy()` does not make another arrangement.

Normal `multi` planning skips this entry.

## `planners/constraint_solver.py` — fits rooms like a puzzle

### What this file does

This planner uses Google OR-Tools. OR-Tools is a library that solves difficult placement puzzles.

Think of it like fitting different rectangular tiles inside one large rectangle while following rules.

### Important functions

#### `constraint_solver()`

Checks whether the request is small enough for this planner, then tries to solve it.

It first tries to keep room sizes balanced. If that cannot find an answer in the allowed work limit, it tries a simpler version.

#### `_solve()`

Builds the room-placement puzzle and asks OR-Tools for an answer.

It checks:

- rooms do not overlap;
- rooms cover the used rectangle;
- minimum room sizes;
- room shape limits;
- important direction requests;
- window access;
- entrance side;
- room connections; and
- closeness to wanted room areas.

#### `_add_adjacency()`

Adds a rule saying that two rooms must share enough wall.

#### `_add_near()`

Adds a rule saying that two rooms must stay near each other.

### Who calls it?

`planner.run_strategy()` calls it through the shared planner list.

If OR-Tools is missing or the request is too large, this planner returns no answer. Other planners still get a chance.

## `planners/rectilinear.py` — makes several simple room patterns

“Rectilinear” only means that the rooms use straight horizontal and vertical sides.

This file provides three planners.

### `open_living_core()`

Tries to place a living space near the middle, with bedrooms and service rooms around it.

If that special shape does not fit, it can use a middle hallway with room rows.

### `side_corridor()`

Places one hallway along the west side and rooms beside it. This can help on narrow plots.

### `zoned_wings()`

Puts bedrooms in one side group and public/service rooms in another, with a hallway between them.

### Helpful private functions

- `_alloc()` shares available width or depth without making rooms smaller than their minimum.
- `_lay_row()` puts rooms next to each other in a row.
- `_lay_column()` puts rooms one below another.
- `_mark_entrance()` chooses a suitable entrance room.

### Who calls these planners?

`ai_client._run_multi_planner()` reaches them through `planner.run_strategy()`.

## `planners/subdivision.py` — keeps cutting a rectangle into rooms

### What this file does

This planner starts with one large rectangle. It cuts that rectangle into two pieces, then keeps cutting pieces until each requested room has one piece.

### Important functions

#### `recursive_subdivision()`

The main planner function.

#### `_partition()`

Tries horizontal and vertical cuts. It stops after a fixed amount of work, so it cannot search forever.

#### `_relationship_order()`

Places strongly connected rooms near each other in the room order before cutting.

#### `_optimize_relationship_assignments()` and `_optimize_all_assignments()`

Try a limited number of room-to-box swaps to improve room connections, directions, and entrance placement.

#### `_fits()`

Checks that one room can use a box without becoming too small or too long and thin.

### Who calls it?

The shared planner list calls it. `ai_client._run_multi_planner()` tries this planner with three nearby seed numbers to get different choices.
## `native_builder.py` — changes room boxes into app drawing data

### What this file does

The `multi` planners return simple room boxes measured in feet. This file changes them into the app's one-floor format.

### Important functions

#### `build_native()`

This is the main function.

It:

1. changes feet into canvas pixels;
2. creates room records;
3. finds shared walls;
4. cuts matching door openings into both rooms;
5. adds required room-to-room doors;
6. adds the few extra doors needed so every room can be reached;
7. adds windows to outside walls;
8. adds the main entrance;
9. creates room labels; and
10. returns native v1 data.

#### `_shared_wall()`

Checks whether two rooms touch along a useful piece of wall.

#### `_side_is_exterior()`

Checks whether one room side is on the outside edge of the building.

### Who calls it?

`ai_client._run_multi_planner()` calls it after `planner.validate_topology()` accepts a room arrangement.

The result is then checked by `ai_validator.py`.

## `geometry_autofix.py` — fixes small drawing mistakes

### What this file does

This file repairs small problems where the correct answer is clear.

It does not redesign the house.

### Main function

#### `autofix_layout()`

Runs all safe repair helpers and returns the same layout object.

It is designed not to crash. If one repair cannot be made safely, the later validator reports the problem.

### Examples of repairs

- Fix a zero-size room when its saved width or height still shows the intended size.
- Change wall names such as `north` and `west` into the app's names `top` and `left` when the north direction is clear.
- Keep wall openings inside their walls.
- Sort and join overlapping wall openings.
- Move openings away from corners.
- Copy an inside wall opening to the room on the other side.
- Separate some overlapping room boxes with the smallest safe boundary move.
- Move a door onto its real opening.
- Move or resize furniture so it stays inside a room.

### Who calls it?

- `ai_client._run_pass()`; and
- the furniture step inside `ai_client.generate_layout()`.

Every repaired plan must still pass `ai_validator.py`.

## `ai_validator.py` — the strict plan checker

### What this file does

This is the final checker for AI-made one-floor layouts.

It does not change the plan. It only returns problems.

### Important functions

#### `validate_layout()`

Checks the actual drawing data.

It checks things such as:

- correct version and project information;
- safe file size and list sizes;
- unique IDs;
- valid room boxes;
- no large room overlaps;
- valid walls and openings;
- supported flooring and furniture;
- doors sitting near real wall openings;
- furniture staying inside rooms;
- valid labels and north direction; and
- safe number and text limits.

It returns at most 40 different errors. An empty list means the layout passed.

#### `validate_design()`

Checks house-level rules that simple file checking cannot cover.

It checks things such as:

- requested room counts;
- requested plot size;
- entrance and movement between rooms;
- outside windows and air flow;
- Vastu direction requests;
- requested room connections; and
- complete furniture needs when furniture is expected.

The `phase` value can ask it to check only the room shell or the complete furnished plan.

#### `is_allowed_furniture_overlap()`

Allows sensible cases, such as an item sitting on a table, while rejecting large overlaps between solid furniture items.

### Who calls it?

- `ai_client.generate_layout()`;
- `ai_client._run_pass()`;
- `ai_client._run_multi_planner()`; and
- several offline self-checks.

## `scoring.py` — chooses the best valid plan

### What this file does

This file compares plans that have already passed the important checks.

A high score cannot rescue an invalid plan. Invalid plans are removed first.

### Important functions

#### `score()`

Gives points for:

- room sizes close to the wanted sizes;
- requested rooms touching each other;
- less wasted hallway space;
- access to daylight;
- bedroom privacy;
- correct Vastu areas;
- useful furniture; and
- a compact building shape.

It also returns notes about compromises.

#### `fingerprint()`

Creates a short identity for a room arrangement. Two plans with the same room boxes get the same identity even if their room list is in a different order.

#### `rank_and_diversify()`

Sorts valid plans from best to worst and removes repeated arrangements. It keeps up to three different choices.

### Who calls it?

`ai_client._run_multi_planner()`.

## `asset_catalog.py` — the supported furniture list

### What this file does

This file gives the AI, fixer, and checker one shared list of furniture that the app actually has.

### Important parts

#### `Asset`

Stores:

- exact furniture name;
- easy search name;
- width and depth;
- suitable room types; and
- whether the item is a door.

#### `CATALOG`

The ready-to-use furniture list.

#### `dimensions()`

Returns the known size of one furniture item.

#### `assets_for_role()`

Returns furniture that fits a room purpose, such as bedroom or kitchen.

#### `is_supported()`

Checks whether an exact furniture name is allowed.

### Who calls it?

- `ai_client.py`, when telling the AI what furniture names exist;
- `geometry_autofix.py`, when placing furniture; and
- furniture-checking code.

## `native_v2.py` — joins several floors into one project

### What this file does

This file takes several finished one-floor layouts and places them inside one v2 project.

### Important functions

#### `default_floor_name()`

Returns names such as Ground Floor and First Floor.

#### `build_multi_floor_document()`

Creates:

- one unique ID for each floor;
- one unique name for each floor;
- a different height for each floor;
- the one-floor canvas stored inside each floor;
- Ground Floor as the active floor; and
- empty cross-floor links.

### Who calls it?

`ai_client.generate_multi_floor_layout()`.

### What it does not do

It does not place rooms. It does not add working stairs. It does not check that stairs line up between floors.

# Important files outside `generate_layout`

## `toolbar.py` — creates the Generate Layout tab

`setup_toolbar()` creates every editor tab.

For this feature it calls:

```text
GenerateLayoutTab(...).build(gen_layout_body)
```

It passes the same model, tools, view, and actions used by the rest of the editor.

## `top_action_toolbar.py` — opens the tab

`_on_open_layout_tab()` switches the side panel to **Generate Layout**.

It does not create a plan.

## `app.pyw` — creates the complete editor

### Important work

`MiniAutoCADApp.__init__()` creates:

- the drawing model;
- canvas view;
- drawing tools;
- action history;
- controller;
- one `LayoutSerializer`;
- 3D viewer connection;
- autosave; and
- toolbars.

### Important function after AI loading

#### `_on_project_mutation()`

Runs after the AI plan has been loaded successfully.

It:

- refreshes floor controls;
- schedules autosave;
- refreshes detected rooms; and
- refreshes the 3D view when it is open.

## `action.py` — shares the layout loader

`ActionManager` has a `serializer` field.

When `LayoutSerializer` is created, it puts itself into `actions.serializer`.

That is how `GenerateLayoutTab` finds the existing loader. The AI tab does not create a second loader or a second project state.

## `layout_serializer.py` — loads the plan and rebuilds the canvas

### What this file does

This file changes saved project data into visible canvas objects.

For an AI result, it performs an all-or-nothing load: either the complete new project is loaded, or the old project is restored.

### Important functions

#### `load_document()`

This is the main loading function.

It:

1. checks the project data with `layout_schema.validate_document()`;
2. remembers the old project and old canvas;
3. replaces the official project data;
4. redraws the active floor;
5. restores the old data if redraw fails;
6. clears old undo and redo history; and
7. tells the app that the project changed.

#### `_canvas_from_geometry()`

Gets the one-floor canvas stored inside a floor. It can also rebuild a canvas view from the newer v2 room and wall lists.

#### `_materialize_active_floor()`

Finds the selected floor and sends it to `deserialize_layout()`.

#### `deserialize_layout()`

Clears the old drawing and recreates:

- shapes;
- rooms;
- room links;
- furniture;
- windows;
- text; and
- compass direction.

#### `activate_floor()`

Saves the current floor, selects another floor, and redraws it.

#### `serialize_layout()`

Changes the current project into data that can be backed up, autosaved, or sent to the 3D viewer.

#### `atomic_write_document()`

Writes a complete file safely. A failed write should not leave a half-written file that looks usable.

## `project_state.py` — keeps the official project in memory

### What this file does

This file owns the current v2 project while the app is running.

It returns copies to other code so those callers cannot accidentally change the official project without checking it.

### Important functions

#### `ProjectState.replace()`

Checks a complete project, then replaces the old project.

#### `snapshot()`

Returns a safe copy of the current project.

#### `replace_active_geometry()`

Replaces only the drawing data for the selected floor.

#### `FloorManager`

Handles adding, copying, selecting, renaming, moving, and deleting floors.

### Who calls it?

Mostly `LayoutSerializer`.

## `layout_schema.py` — rules for a valid project

“Schema” means the required shape and rules of the saved project data.

### Important functions

#### `validate_document()`

Checks incoming project data. It can also change an older one-floor v1 document into the current v2 project shape.

#### `validate_v2()`

Checks:

- floors;
- unique floor names and IDs;
- floor heights;
- selected floor;
- room and wall IDs;
- links between objects;
- stairs;
- sun settings; and
- links between floors.

#### `new_project()`

Creates the empty project used by the **New design** button.

## `app_paths.py` — decides where app files are stored

`AppPathManager` returns folders for:

- user-saved layouts;
- autosave;
- backup files; and
- generated layout files.

It also creates those folders when needed.
# Files in this folder that are not part of the live AI path

## `service.py` — manual shape generator

This file belongs to the same Generate Layout area, but it does not use Gemini.

### `GenerateLayoutService.generate_rectangle()`

Takes a length and breadth, changes them into pixels, draws one rectangle, adds labels and side measurements, and records the action for undo.

### `GenerateLayoutService.generate_compass_layout()`

Takes north, south, east, and west side lengths and draws a matching outline.

These functions do not call `ai_client.py`, AI planners, or the AI checker.

## `storage.py` — a save helper that is not currently connected

### What it contains

#### `GeneratedLayoutStorage.ensure_dir()`

Creates or finds the generated-layout folder.

#### `GeneratedLayoutStorage.save_json()`

Writes a generated result with a time and random short ID in its filename.

### Important current truth

The running AI path does **not** call these functions.

The real successful path is:

```text
save the old project as before_ai_apply_*.json
  → load the new AI result
  → run the normal app autosave
```

Do not expect every AI answer to appear in the `generated_layouts` folder unless future code connects `save_json()` to the AI tab.

## `__init__.py`

This only marks `generate_layout` as a Python package. It has no planning logic.

## `__pycache__`

Python creates this folder automatically to make later starts faster.

It is not source code. Do not edit it.

# Existing offline checks

“Offline” means these checks do not contact Gemini and do not spend Google quota.

## `_multi_pipeline_check.py`

Its `main()` function checks that:

- the older comb builder still makes a valid plan;
- `multi` mode can make several valid choices;
- the highest valid score wins;
- the same request and seed give the same result;
- clear user facts beat AI guesses;
- AI-added optional rooms can be removed; and
- the open-living arrangement stays valid for its example request.

It calls `_run_multi_planner()` directly.

Several other files have a small self-check at the bottom. These include:

- `design_spec.py`;
- `feasibility.py`;
- `native_builder.py`;
- `native_v2.py`;
- `scoring.py`; and
- planner files.

These checks are useful when changing one part of the pipeline.

# Why a bad result should not replace the user's work

Many separate checks protect the project:

1. Settings such as timeout and token count are kept inside safe limits.
2. Unknown planner names are rejected.
3. Every AI call uses a fixed call limit.
4. Every request uses a fixed time limit.
5. Cancellation is checked before and after slow work.
6. Bad or incomplete JSON is rejected.
7. The AI wish list is compared with the user's real words.
8. Impossible room lists are rejected before planning.
9. Every room arrangement is checked before drawing data is built.
10. The complete one-floor plan is checked again.
11. Repair attempts are limited.
12. Old request numbers cannot replace newer work.
13. The current project must be backed up before AI replacement.
14. The official project format is checked before loading.
15. If loading or drawing fails, the old project and old canvas are restored.

These checks may look repeated, but they protect different steps.

# Which file should I change?

| If you want to change... | Start with... |
|---|---|
| AI buttons, chat, progress, cancel, or floor buttons | `tab.py` |
| Model name, time limits, call limits, or planner choice | `ai_client.py` |
| Rules given to Gemini in `comb` mode | `architecture_rules.md` |
| Fields in the `multi` house wish list | `design_spec.py` |
| Practical minimum room sizes | `feasibility.py` |
| The middle-hallway `comb` drawing | `layout_engine.py` |
| Shared planner room and result objects | `planner.py` |
| Exact puzzle-based room fitting | `planners/constraint_solver.py` |
| Open core, side hallway, or room wings | `planners/rectilinear.py` |
| Rectangle-splitting planner | `planners/subdivision.py` |
| Doors and windows made from placed rooms | `native_builder.py` |
| Small automatic drawing fixes | `geometry_autofix.py` |
| Rules that accept or reject AI layouts | `ai_validator.py` |
| How valid choices are compared | `scoring.py` |
| Supported furniture names and sizes | `asset_catalog.py` |
| How several floors are joined | `native_v2.py` |
| How a checked project is loaded and drawn | `layout_serializer.py` |
| Official project and floor rules | `layout_schema.py` and `project_state.py` |

When changing one file, also read the checker that protects its output. For example, when changing doors in `native_builder.py`, also read the door checks in `ai_validator.py`.

# Best reading order for a new developer

You do not need to read every file at once. Use this order:

1. Read [AI layout generation](../../../docs/ai-layout-generation.md) for the short feature story.
2. Read `tab.py::_on_ai_generate()` to see how a request starts.
3. Read `tab.py::_poll_ai_queue()` to see how a result is applied.
4. Read `ai_client.py::generate_layout()` to see the main choices.
5. For `comb`, read `layout_engine.py::build_layout()`.
6. For `multi`, read `design_spec.py`, `feasibility.py`, and `ai_client.py::_run_multi_planner()`.
7. Read the planner file you care about.
8. Read `native_builder.py::build_native()`.
9. Read `ai_validator.py::validate_layout()` and `validate_design()`.
10. Read `layout_serializer.py::load_document()` to see how the plan reaches the canvas.

# Simple debugging order

When an AI layout fails, check these questions in order:

1. Did `tab.py` send the correct user message?
2. Did it send the correct old plan and old `DesignSpec`?
3. Was the selected mode `comb` or `multi`?
4. Did Gemini return valid JSON?
5. Did the cleaned wish list match the user's request?
6. Did `feasibility.py` say the rooms can fit?
7. Which planners returned a possible arrangement?
8. Why did `validate_topology()` reject an arrangement?
9. Did `native_builder.py` create correct walls, openings, doors, and windows?
10. What did `geometry_autofix.py` change?
11. What was the first error from `ai_validator.py`?
12. Was the request cancelled or old by the time it returned?
13. Did the old-project backup succeed?
14. Did `layout_schema.py` accept the project?
15. Did `layout_serializer.py` fail while rebuilding the canvas?

Following this order matches the real code path. It helps find the first cause instead of adding fixes in several unrelated files.

# Final summary

The most important files are:

```text
tab.py
  Starts the request and safely applies the result.

ai_client.py
  Controls Gemini calls and connects all planning steps.

design_spec.py
  Keeps a clean list of what the user asked for.

feasibility.py
  Checks whether the request can fit.

layout_engine.py or planners/*
  Places the rooms.

native_builder.py
  Adds exact app drawing data, doors, and windows for multi mode.

geometry_autofix.py
  Fixes small clear mistakes.

ai_validator.py
  Rejects unsafe or incorrect plans.

layout_serializer.py
  Backs up, loads, and redraws the accepted project.
```

In one sentence:

> **The AI understands the user's words, local Python code builds the plan, checkers approve it, and the normal project loader shows it on the canvas.**
