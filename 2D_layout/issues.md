# Tkinter 2D Layout Maker — Verified Issue List


### 1. Windows are not real editable objects

**Status: Confirmed issue.**

Windows are saved only as unnamed gaps in `wall_erased_regions`. The application now draws blue window symbols for unclaimed gaps when a layout is loaded, but these symbols are not real window objects.

Because of this, a user cannot directly place, select, move, resize, change, or delete a window. Erasing a wall during the current session also creates only a gap; the blue window symbol is inferred when the file is loaded again.

**Needed improvement:** Add a proper Window tool and save each window with its room or wall, size, position, and window type. Doors and gates should eventually use the same clear opening system instead of depending on furniture image names.

### 2. There is no visible “Delete Selected” button

**Status: Confirmed usability issue, but deletion itself exists.**

Furniture and doors can already be removed by:

- Right-clicking the item and choosing **Delete**.
- Selecting the item and pressing the **Delete** key.

The missing part is a clear Delete/Remove button in the Edit toolbar. A beginner may reasonably believe deletion is unavailable because the existing commands are hidden in a right-click menu or keyboard shortcut.

**Needed improvement:** Add a visible **Delete Selected** button and show a short hint about the Delete key.

### 3. Selected furniture or gates cannot be dragged

**Status: Existing feature, not a missing feature.**

Furniture and door images are locked after placement. To move one, the user must right-click it, choose **Edit**, and then drag it. Pressing Enter commits or locks it again. Furniture attached to a room also moves when the room is moved.

The real problem is that this workflow is not obvious.

**Needed improvement:** Show an “Item locked — right-click and choose Edit to move” message, or provide a visible **Move/Edit Selected** button.

### 4. Zoom makes floors or furniture leave their correct position

**Status: Partly correct; a flooring zoom bug is confirmed.**

Walls, drawing points, the canvas area, and furniture already have zoom-update logic. The broad statement that every object always moves incorrectly is therefore not accurate.

However, floor textures have a real problem: the zoom code looks for a flooring update action that does not exist under that name. As a result, a floor image can move with its anchor while keeping the wrong visual size, making it drift away from walls or room boundaries.

Zoom also has no safe minimum/maximum and no **Reset View** or **Fit Design** button, so extreme zoom levels can make the design difficult to recover.

**Needed improvement:** Connect the correct flooring resize action, add zoom limits, and add **Reset View** and **Fit Design** controls.

## 5. There is no feature to replicate a design

**Status: Partly correct; individual duplication exists.**

The application already supports several smaller duplication actions:

- Furniture and doors: right-click and choose **Duplicate**.
- Lines and text: use their right-click duplicate actions.
- Selected furniture and basic shapes: use copy and paste.

What is missing is a command to duplicate an entire room, a group of rooms, or the complete floor plan in one action.

**Needed improvement:** Optionally add **Duplicate Room**, **Duplicate Selection**, and **Duplicate Layout** commands. This is useful for repeated bedrooms, apartments, and upper floors, but it is less urgent than data-loss and drawing problems.

## 6. Problems with the Draw tools

### 6a. The Line tool does not snap to existing endpoints

**Status: Confirmed issue.**

The Line tool uses the exact mouse-click position. It does not automatically pull the new point onto a nearby line endpoint or grid point. Polygon tools already have better snapping support, but the normal Line tool does not use it.

**Needed improvement:** Add endpoint, midpoint, grid, straight-angle, and perpendicular snapping to the Line tool. Show a small visual marker when snapping occurs.

### 6b. Two lines cannot be properly joined

**Status: Partly correct.**

Two lines can be placed so they look as if they touch, but they remain separate objects. There is no **Join Lines** command and no shared connection between their endpoints. Moving or editing one line does not keep the other line connected.

The Line tool also turns itself off after one line is completed. This makes drawing several connected wall segments unnecessarily slow because the user must activate the tool again.

**Needed improvement:** Keep Line mode active until Escape/right-click is pressed, snap each new line to the previous endpoint, and add a **Join Lines** command.

### 6c. Closed Draw lines do not become real rooms

**Status: Confirmed issue.**

When Line segments return near their starting point, the application can create a closed shape. However, that shape is only a drawing polygon. It is not a real room.

It therefore does not receive normal room behavior such as a room name, wall thickness, room movement, proper openings, room flooring ownership, or reliable furniture attachment. The application has separate room/polygon tools, so room creation itself is not completely missing; the problem is that Draw lines cannot be converted into one.

**Needed improvement:** Add **Create Room from Closed Lines** and validate that the lines form one clean closed boundary.

## Additional confirmed issues found during the audit

### 7. Furniture cannot be resized after placement

**Status: Confirmed issue.**

Furniture has an Edit mode for movement and rotation, but its resize action and resize handles are disabled. Users must accept the standard item size.

**Needed improvement:** Restore visible resize handles, keep the item proportions by default, and allow exact width/depth entry.

### 8. Furniture Delete and Duplicate cannot be undone

**Status: Confirmed issue.**

Undo and Redo buttons exist, but furniture/door deletion and duplication are not added to the undo history. A user can accidentally delete an item and find that Undo does not restore it.

**Needed improvement:** Record furniture and door Delete/Duplicate actions so Undo and Redo work consistently.

### 9. Dashed lines become solid after save and reload

**Status: Confirmed issue.**

The Draw toolbar allows dashed lines, but the saved file records every shape as solid. When the file is opened again, dashed lines lose their appearance.

**Needed improvement:** Save and restore each line's real style, including solid, bold, dashed, color, width, and arrow direction.

### 10. Loading the wrong file can clear the current drawing

**Status: Confirmed high-risk issue.**

The loader clears the canvas before checking that the selected file is a valid native Layout Maker file. Choosing an incompatible or incomplete JSON file can therefore remove the current drawing before the problem is reported.

For example, a Home Quest `.hq.json` file is not a native Layout Maker file and should be rejected before anything on the canvas changes.

**Needed improvement:** Validate the complete file first, show a clear error if it is not native Layout Maker JSON, and replace the current drawing only after validation succeeds. Also offer a save/backup confirmation before loading another layout.

## Features that already exist and should not be reported as completely missing

### Moving furniture and doors

Use **Right-click → Edit**, then drag the item. Press Enter to lock it again. The feature exists, but the application should explain it more clearly.

### Deleting furniture and doors

Use **Right-click → Delete** or select the item and press the Delete key. A visible toolbar button is still needed.

### Duplicating individual items

Furniture, doors, lines, text, and basic shapes already have duplication or copy/paste support. Only whole-room and whole-layout duplication are missing.

### Snapping in Polygon tools

Polygon and Vastu Polygon tools already have snapping support. The missing snapping problem mainly affects the standard Line tool.

### Creating rooms by other tools

The application has room/polygon creation workflows. The confirmed problem is specifically that closed Line-tool drawings cannot be converted into proper rooms.

## Problems fixed earlier

### Window symbols were invisible after loading



