# User experience issues in the 2D Layout Maker

## High priority

### 1. Length input does not support feet and inches together
Room dimensions accept only one decimal number in the selected unit. A common value such as `5 ft 2 in` or `5' 2"` is rejected, so users have to calculate `5.17 ft` themselves.

**Expected:** Accept feet and inches as separate fields or understand common formats, then show the normalized value before creating the room.

### 2. The length/breadth boxes show no visible text while typing
The typed value in the Length and Breadth boxes is effectively invisible, so users cannot see what they entered. The code does set a dark text colour, so this looks like a contrast problem where the text colour matches the box background under the current theme (light text on a light field, or the placeholder colour being reused for real input).

**Expected:** Force a fixed dark text colour on a plain white field for these entries so typed numbers are always readable, and check the same boxes in the Coordinates and Generate tabs.

### 3. Polygon drawing is difficult to finish and can create invalid shapes
A polygon is finished only by clicking very close to its first point. This is easy to miss, especially at a different zoom level. The editor also accepts crossed edges, repeated points and zero-length edges, which can produce incorrect area and perimeter values.

**Expected:** Provide visible **Finish** and **Cancel** actions, highlight the closing point clearly, and reject invalid polygons with a useful message.

### 4. Sidebar resizing can stop responding after dialogs or file loading
The sidebar uses a manual mouse grab for resizing. It releases that grab only on the normal mouse-release path, with no focus-loss recovery. A file picker or modal dialog can interrupt this interaction and leave resizing unreliable.

**Expected:** Always clean up the drag state when focus changes or a dialog opens/closes. Reproduce this with the exact JSON file before changing the code.

### 5. Vastu failures are hidden from the user
The Vastu workflow exists, but many setup and refresh errors are silently ignored. Controls can disappear, remain disabled or stop updating without explaining what failed. This makes the feature look completely broken.

**Expected:** Show a short error with a recovery action, explain why a control is disabled, and test 8/16/32 zones on rectangular and irregular plans.

### 6. The 2D plan and 3D viewer cannot be used together
Plan and 3D View occupy the same area and one is hidden when the other opens. A user cannot adjust a wall or room while watching the 3D result.

**Expected:** Add an optional resizable split view. Keep the existing tab view for smaller screens.

## Medium priority

### 7. The user guide is only partly bilingual and blocks the editor
New-feature cards and shortcuts include Hindi, but the Tools and Vastu sections are still mostly English. The guide is also modal, so users cannot follow its steps while working on the plan.

**Expected:** Provide English and Hindi for every section and allow the guide to stay open beside the editor.

### 8. Some loaded rooms can lose normal editing behaviour without warning
If a saved room cannot be rebuilt as a full room object, the loader silently draws a basic rectangle and still reports a successful load. That fallback has fewer labels and interactions, so dragging or editing may behave differently after loading certain files.

**Expected:** Report which room could not be restored and why. Do not silently downgrade an editable room.

### 9. Balcony validation happens after the room is created
The editor creates the room before checking some balcony fields. If a depth is entered without selecting a side, an error appears but the room remains. An invalid depth may only be printed to the console.

**Expected:** Validate all room and balcony inputs first, then create everything in one step.
