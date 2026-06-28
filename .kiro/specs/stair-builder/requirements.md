# Requirements Document

## Introduction

Home Quest currently places a staircase as a single furniture catalog item (`stairs`, `STAIRS_CATALOG_ID`) — a straight box scaled and rotated like any other prop and dropped between two floors. This is not a valid stair: it ignores the real inter-storey height, does not reliably land on the upper floor, and only recently gained a rectangular stairwell cut through the ceiling slab and upper floor finish.

This feature redesigns stair placement into a dedicated, path-based architectural tool. The user draws a 2D path from a start point on the lower floor to an end point on the upper floor; intermediate points define turns and landings. From that path the application generates a real staircase (straight, L-shaped, U-shaped, or custom multi-segment) sized to the actual inter-storey height so the top step lands flush on the upper floor. The tool automatically cuts a clean stairwell void through both floor slabs (the lower floor's ceiling slab and the upper floor's floor finish), produces clean finished geometry, and supports first-person walkability up the generated path.

The feature also bundles four rendering/finish correctness fixes the user reported in the same area: tight-fitting door/window cutouts, elimination of door/window flicker (z-fighting), removal of stray lines on wall surfaces, and a clean continuous roof/ceiling surface free of internal grid/seam lines.

The system uses a 2D SVG editor (plan, centimeters) backed by a Zustand store, and a `react-three-fiber` 3D viewer (meters, `CM_TO_M = 0.01`). Floors are stacked by `elevationCm`; the active floor lives in the working set while other floors are parked in `floorData`. `STORY_HEIGHT_CM = 300`.

## Glossary

- **Plan_Unit**: A length in centimeters in the 2D plan coordinate space. Converted to 3D meters via `CM_TO_M = 0.01`.
- **UI_Store**: The Zustand store slice that holds editor UI state, including the `activeTool` selection.
- **Lower_Floor**: The storey on which a staircase begins (its `START` point). Has base elevation `elevationCm`.
- **Upper_Floor**: The storey on which a staircase ends (its `END` point), immediately above the Lower_Floor by `STORY_HEIGHT_CM` (300 cm) unless floors have custom elevations.
- **Inter_Storey_Height**: The vertical distance in cm from the Lower_Floor base to the Upper_Floor base, equal to `Upper_Floor.elevationCm − Lower_Floor.elevationCm`.
- **Stair_Path**: An ordered list of two or more 2D plan points (cm) drawn by the user: the first point is `START` (on the Lower_Floor), the last is `END` (on the Upper_Floor), and any middle points define turns/landings.
- **Stair_Entity**: The persisted data model for a generated staircase: its Stair_Path, ordered Flights and Landings, total rise, width, and the floor ids it connects. Stored per-floor like other geometry.
- **Flight**: A continuous run of steps with constant direction between two consecutive Stair_Path points (or between a point and a Landing), each step having a uniform Rise and Going.
- **Landing**: A flat platform inserted at a turn point or between Flights, level with the top of the Flight below it.
- **Rise**: The vertical height of a single step in cm.
- **Going**: The horizontal tread depth of a single step in cm.
- **Stairwell_Void**: The polygonal opening cut through the Lower_Floor's ceiling slab and the Upper_Floor's floor finish so the staircase passes between storeys.
- **Stair_Tool**: The editor tool (a new value of the `Tool` union, e.g. `'stair'`) that drives the multi-point 2D Stair_Path drawing interaction.
- **Stair_Builder**: The service that converts a validated Stair_Path and Inter_Storey_Height into Flights, Landings, and a Stairwell_Void footprint.
- **Stair_Renderer**: The 3D component that renders a Stair_Entity (replacing/superseding `StairsPrefab` for new stairs).
- **Walkthrough_System**: The first-person walkthrough logic (`useFirstPerson`, `stairRampHeightAt`) that raises the player's standing height along a staircase.
- **Opening_Punch**: The analytic wall-opening logic (`createWallGeometry` in `extrusion.ts`) that cuts door/window/vent holes without a CSG library.
- **Slab_Renderer**: The per-storey ceiling slab and floor finish rendering (`SlabMesh`, `FloorMesh` in `FloorScene.tsx`).
- **Roof_Surface**: The topmost ceiling/roof shown above the highest storey.
- **Legacy_Stair_Item**: A staircase saved in an existing plan as a furniture item with `catalogId === 'stairs'`.

## Requirements

### Requirement 1: Stair Tool and 2D path drawing

**User Story:** As a home designer, I want to draw a path from the lower floor to the upper floor, so that the app builds a real staircase along the path I choose.

#### Acceptance Criteria

1. WHEN the user selects the Stair_Tool, THE UI_Store SHALL set `activeTool` to the Stair_Tool identifier, and no other editor tool SHALL be active while `activeTool` references the Stair_Tool.
2. WHILE the Stair_Tool is active AND no Stair_Path is in progress, WHEN the user clicks a plan location that is not occupied by an existing Stair_Entity, THE Stair_Tool SHALL record that location, in centimeters, as the `START` point of a new Stair_Path on the Lower_Floor.
3. WHILE a Stair_Path is being drawn, WHEN the user clicks an additional plan location, THE Stair_Tool SHALL append that location as an intermediate point of the Stair_Path.
4. WHILE a Stair_Path is being drawn, THE Stair_Tool SHALL render a live preview of the path from the `START` point through every recorded point to the current cursor position, updated on each cursor-position change.
5. WHEN the user performs a finishing action (double-click on the plan or pressing the Enter key) while the Stair_Path contains at least two distinct points, THE Stair_Tool SHALL record the cursor location as the `END` point and request stair generation.
6. WHILE a Stair_Path is being drawn, WHEN the user presses the Escape key, THE Stair_Tool SHALL discard the in-progress Stair_Path, record no Stair_Entity, and return to an idle state holding no recorded points.
7. IF the user performs a finishing action while the Stair_Path contains fewer than two distinct points, THEN THE Stair_Tool SHALL reject the finishing action, retain the in-progress Stair_Path, and present an indication that at least two distinct points are required.
8. THE Stair_Tool SHALL treat two plan points as distinct only when they are separated by at least 1 cm in plan coordinates.

### Requirement 2: Stair entity data model

**User Story:** As a developer, I want stairs stored as a real architectural entity instead of a furniture box, so that the app can reason about flights, landings, and rise.

#### Acceptance Criteria

1. THE Stair_Entity SHALL store the Stair_Path, an ordered list of at least one Flight, an ordered list of zero or more Landings, a total rise greater than 0 cm, a stair width in the range 60 cm to 500 cm inclusive, and the `EntityId` of the Lower_Floor and the Upper_Floor it connects.
2. WHEN a plan is saved, loaded, or the active floor is switched, THE system SHALL preserve every Stair_Entity such that each stored field (Stair_Path, Flights, Landings, total rise, width, floor ids) is identical before and after the operation.
3. WHEN a Stair_Entity is created, THE system SHALL assign it an `EntityId` that is unique across all Stair_Entities on every floor in `floorData` and the active floor.
4. WHERE a plan contains a Legacy_Stair_Item, THE system SHALL render and walk that item using the existing furniture-based behavior AND SHALL NOT convert it into a Stair_Entity.
5. THE total rise stored on the Stair_Entity SHALL equal the Inter_Storey_Height between its Lower_Floor and Upper_Floor, which for adjacent default storeys equals `STORY_HEIGHT_CM` (300 cm).
6. IF a stair generation request would produce a total rise that does not equal the Inter_Storey_Height, THEN THE system SHALL NOT create the Stair_Entity AND SHALL report a sizing error.
7. IF a stair generation request would produce a width outside 60–500 cm or fewer than one Flight, THEN THE system SHALL NOT create the Stair_Entity AND SHALL report a validation error.

### Requirement 3: Stair geometry generation sized to the storey

**User Story:** As a home designer, I want the generated staircase to fit exactly between the two floors, so that the top step lands flush on the upper floor.

#### Acceptance Criteria

1. WHEN a valid Stair_Path is completed, THE Stair_Builder SHALL generate Flights whose combined Rise equals the Inter_Storey_Height within ±0.1 cm so that the top step is level with the Upper_Floor base.
2. THE Stair_Builder SHALL compute a positive integer number of steps so that each step's Rise is within the range 15 cm to 19 cm inclusive.
3. THE Stair_Builder SHALL distribute steps so that every step in the staircase has a Rise that differs from every other step's Rise by no more than 0.1 cm.
4. THE Stair_Builder SHALL generate one Flight per straight segment of the Stair_Path.
5. WHERE the Stair_Path contains an intermediate point, THE Stair_Builder SHALL insert a Landing at that point between the adjoining Flights.
6. THE Stair_Builder SHALL render and walk the staircase with a constant width equal to the Stair_Entity width, within ±0.1 cm, along every Flight and Landing.
7. IF no positive integer number of steps produces a per-step Rise within the range 15 cm to 19 cm inclusive for the current Inter_Storey_Height, THEN THE Stair_Builder SHALL NOT generate Flights and SHALL present an error indication that the staircase cannot be sized to the storey, while retaining the Stair_Path unchanged.

### Requirement 4: Multiple stair types from the path shape

**User Story:** As a home designer, I want straight, L-shaped, U-shaped, and custom staircases, so that the staircase matches my floor layout.

#### Acceptance Criteria

1. WHEN the Stair_Path has exactly two points separated by at least 10 mm, THE Stair_Builder SHALL generate a single straight Flight.
2. WHEN the Stair_Path has exactly three points containing exactly one turn, where a turn is a vertex at which the angle between the two adjacent segments deviates from 180 degrees by more than 1 degree, THE Stair_Builder SHALL generate an L-shaped staircase with exactly one Landing positioned at that turn.
3. WHEN the Stair_Path has four or more points containing exactly two turns whose successive direction changes have opposite rotational sense (one clockwise and one counter-clockwise), THE Stair_Builder SHALL generate a U-shaped staircase with exactly one Landing positioned at each of the two turns.
4. WHERE the Stair_Path has four or more points and does not satisfy the U-shaped condition in criterion 3, THE Stair_Builder SHALL generate a multi-segment staircase containing exactly one Flight per straight segment and exactly one Landing per turn.
5. WHEN the Stair_Builder generates Flights and Landings, THE Stair_Builder SHALL position them so that the horizontal centerline of every Flight and Landing lies within 1 mm of the drawn Stair_Path.
6. IF the Stair_Path has fewer than two points, or any two consecutive points are separated by less than 10 mm, THEN THE Stair_Builder SHALL NOT generate any Flight or Landing AND SHALL present an error indication identifying the invalid Stair_Path.

### Requirement 5: Automatic stairwell void in both slabs

**User Story:** As a home designer, I want the app to open the floor between storeys automatically, so that the staircase is not blocked by a slab.

#### Acceptance Criteria

1. WHEN a Stair_Entity is created, THE Stair_Builder SHALL compute a Stairwell_Void footprint equal to the horizontal-plane union of the projected footprints of every Flight and Landing belonging to that Stair_Entity, such that no point of any Flight or Landing lies outside the Stairwell_Void footprint.
2. WHEN a Stair_Entity exists, THE Slab_Renderer SHALL cut the Stairwell_Void through the Lower_Floor's ceiling slab as a hole matching the Stairwell_Void footprint.
3. WHEN a Stair_Entity exists, THE Slab_Renderer SHALL cut the Stairwell_Void through the Upper_Floor's floor finish so that, at every footprint vertex, the horizontal offset between the floor-finish cut boundary and the ceiling-slab cut boundary is 0 millimetres.
4. IF any point of the Stairwell_Void footprint lies outside the room polygon it is cut from, THEN THE Stair_Builder SHALL NOT create the Stair_Entity, SHALL leave both the ceiling slab and the floor finish uncut, AND SHALL return a validation error indicating that the stairwell void exceeds the room boundary.
5. WHEN a Stair_Entity is deleted and no other Stair_Entity's Stairwell_Void overlaps the affected footprint, THE Slab_Renderer SHALL restore the affected ceiling slab and floor finish to a continuous surface with zero remaining holes over the previously cut footprint.
6. WHEN the Flights or Landings of an existing Stair_Entity are modified, THE Stair_Builder SHALL recompute the Stairwell_Void footprint AND THE Slab_Renderer SHALL re-cut the ceiling slab and floor finish so that both cuts match the recomputed footprint.

### Requirement 6: Clean finished stair geometry

**User Story:** As a home designer, I want the staircase to look finished, so that there are no gaps, overlaps, or visual artifacts.

#### Acceptance Criteria

1. WHEN the staircase geometry is generated, THE Stair_Renderer SHALL position each pair of consecutive Flights and Landings so that the vertical distance between their meeting surfaces is no greater than 1 mm.
2. WHEN the staircase geometry is generated, THE Stair_Renderer SHALL position the top step so that the vertical and horizontal distance between its top surface and the Upper_Floor finish at the edge of the Stairwell_Void is no greater than 1 mm.
3. WHEN the staircase geometry is generated, THE Stair_Renderer SHALL position the bottom step so that the vertical and horizontal distance between its base and the Lower_Floor finish is no greater than 1 mm.
4. WHEN the staircase geometry is generated, THE Stair_Renderer SHALL position stair meshes so that any two non-coincident surfaces are separated by at least 1 mm, and any two surfaces intended to be coplanar share identical vertices, so that no z-fighting occurs.
5. IF the supplied staircase parameters produce geometry where any step, Flight, or Landing cannot be positioned within the 1 mm tolerance of an adjacent element or floor finish, THEN THE Stair_Renderer SHALL withhold the affected staircase from the rendered scene AND return an error indication identifying the unmet connection.

### Requirement 7: First-person walkability

**User Story:** As a home designer in walkthrough mode, I want to walk up the generated staircase, so that I can move between floors naturally.

#### Acceptance Criteria

1. WHILE the player's plan position lies within the horizontal footprint of a Flight (the oriented rectangle spanning the Flight width across the ascent direction and the Flight length along it), THE Walkthrough_System SHALL set the player standing height by linearly mapping the player's fractional progress along the ascent direction (0.0 at the Flight's bottom edge to 1.0 at its top edge) between the Flight's bottom and top elevation.
2. WHILE the player's plan position lies within the horizontal footprint of a Landing, THE Walkthrough_System SHALL set the player standing height to that Landing's elevation.
3. WHEN the player's fractional progress along the final Flight reaches 1.0, THE Walkthrough_System SHALL set the player standing height equal to the Upper_Floor base elevation.
4. IF the player's plan position is outside the footprint of every Flight and Landing of a staircase, THEN THE Walkthrough_System SHALL ignore that staircase when computing standing height.
5. WHILE the player is outside the footprint of every staircase, THE Walkthrough_System SHALL set the player standing height to the base elevation of the storey whose base is nearest the player's current feet height.
6. IF more than one staircase footprint or storey base applies to the player's plan position, THEN THE Walkthrough_System SHALL choose the candidate standing height nearest the player's current standing height so the transition does not teleport the player.

### Requirement 8: Tight-fitting door and window openings

**User Story:** As a home designer, I want doors and windows to sit precisely in their wall cutouts, so that there are no visible gaps around them.

#### Acceptance Criteria

1. WHEN a window opening is placed so that it lies fully within the wall's length and height, THE Opening_Punch SHALL cut a hole whose width and height match the opening's `width` and `height` within a tolerance of ±2 mm, horizontally centred on the opening's offset and with its lower edge at the opening's elevation.
2. WHEN a door opening is placed so that it lies fully within the wall's length, THE Opening_Punch SHALL cut a floor-to-head opening whose width matches the opening's `width` within ±2 mm and whose head is at the opening's `height` above the floor within ±2 mm, horizontally centred on the opening's offset.
3. WHEN a door or window frame is rendered for a placed opening, THE WallMesh SHALL position the frame so that each outer frame edge coincides with the corresponding cut edge within ±2 mm.
4. IF a door or window opening would extend beyond the wall's length or height bounds, THEN THE Opening_Punch SHALL clamp the cut to remain within the wall outline so that the wall mesh stays a single connected surface.
5. WHEN an opening's `width`, `height`, elevation, or offset changes, THE Opening_Punch SHALL re-cut the opening so that the new cut matches the changed values within ±2 mm.

### Requirement 9: Eliminate door and window flicker

**User Story:** As a home designer, I want doors and windows to render stably, so that they do not flicker after placement.

#### Acceptance Criteria

1. WHEN a door or window is placed on a wall, THE WallMesh SHALL assign the frame, the glazing, and the surrounding wall surface to distinct polygonOffset depth slots so that each coplanar surface renders at a unique resolved depth with no shared-depth pixels.
2. WHILE the camera orbits a placed door or window through a full 360-degree rotation and across the supported zoom range, THE WallMesh SHALL render each of the frame, glazing, and wall surfaces with stable front-to-back ordering, exhibiting no alternating or flickering pixels at any camera position.
3. WHERE two coplanar surfaces would otherwise resolve to the same depth, THE WallMesh SHALL separate them by assigning different polygonOffset depth slots such that the same surface renders consistently in front across every camera position, with ordering that does not change between frames.
4. WHEN a door is placed such that its base is coplanar with the floor surface, THE WallMesh SHALL raise the door threshold geometry vertically by DOOR_THRESHOLD_LIFT so that the door base and floor occupy separate depths with no shared-depth pixels.
5. IF more than one door or window is placed on the same coplanar wall face, THEN THE WallMesh SHALL assign each opening's frame and glazing to depth slots that remain distinct from every other opening on that face, so that no two openings share a resolved depth.

### Requirement 10: Remove stray lines on wall surfaces

**User Story:** As a home designer, I want wall surfaces to be clean, so that no stray lines appear after editing operations.

#### Acceptance Criteria

1. WHEN a wall is rendered after an opening or stair operation, THE WallMesh SHALL render each wall face with no internal line of pixels differing in colour from the face material, except at the edges of modeled openings and stairs, observable across the application's supported zoom range.
2. WHILE the camera view direction forms an angle of 0 to 15 degrees with a wall face plane (a grazing angle), THE WallMesh SHALL render that wall face with no artifact line, where an artifact line is a contiguous run of 2 or more pixels differing in colour from the face material.
3. WHEN adjoining walls meet at a vertex, THE WallMesh SHALL render the junction with no background exposed behind the walls and with the mitred faces aligned to within 1 pixel across the supported zoom range.
4. WHERE two wall faces are coplanar or share a mitred corner, THE WallMesh SHALL separate them with per-wall depth offsets so that no z-fighting "fan" artifact appears at any camera angle.
5. WHEN a stair or opening operation is undone, THE WallMesh SHALL render the affected walls with no residual artifact lines from the undone operation.

### Requirement 11: Clean continuous roof surface

**User Story:** As a home designer, I want the roof to look like one clean surface, so that there is no grid or seam pattern on top of the building.

#### Acceptance Criteria

1. WHEN the topmost storey is rendered, THE Slab_Renderer SHALL render the Roof_Surface as a single continuous surface containing no internal edges, grid lines, or shading discontinuities between per-room slab regions, observable from any camera angle and at any zoom level within the application's supported zoom range.
2. WHEN the topmost storey is rendered, THE Slab_Renderer SHALL render the Roof_Surface with no dotted or solid seam lines at shared wall centerlines, observable from any camera angle and at any zoom level within the application's supported zoom range.
3. WHILE the camera views the Roof_Surface, THE Slab_Renderer SHALL render it with no z-fighting artifacts (no flickering and no alternating surfaces) between adjacent slab regions at any camera angle and at any zoom level within the application's supported zoom range.
4. WHEN a room on the topmost storey is added, removed, or has its boundary changed, THE Slab_Renderer SHALL regenerate the Roof_Surface such that criteria 1 through 3 continue to hold.

### Requirement 12: Validation and error handling

**User Story:** As a home designer, I want clear feedback when a staircase cannot be built, so that I can correct the path instead of getting broken geometry.

#### Acceptance Criteria

1. IF the `START` point of the Stair_Path does not lie within a room polygon of the Lower_Floor OR the `END` point does not lie within a room polygon of the Upper_Floor, THEN THE Stair_Tool SHALL report a validation error and SHALL NOT create a Stair_Entity.
2. IF the Inter_Storey_Height is less than or equal to 0 cm, THEN THE Stair_Builder SHALL report a validation error and SHALL NOT create a Stair_Entity.
3. IF the total horizontal length of the Stair_Path is less than the sum of the Goings required for the number of steps computed under Requirement 3 (Rise within 15 cm to 19 cm inclusive), THEN THE Stair_Builder SHALL report a validation error and SHALL NOT create a Stair_Entity.
4. IF any segment of the Stair_Path intersects a wall, THEN THE Stair_Tool SHALL display a warning identifying the intersected segment AND SHALL create the Stair_Entity only after the user confirms the warning.
5. WHEN a validation error is reported, THE Stair_Tool SHALL retain the in-progress Stair_Path unchanged AND SHALL remain the active tool so the user can adjust the path.
6. WHEN a validation error is reported, THE Stair_Tool SHALL display an error message identifying which validation condition failed.

### Requirement 13: Multiple stairs, floor switching, and history

**User Story:** As a home designer, I want to place several staircases and undo my changes, so that the tool behaves like the rest of the editor.

#### Acceptance Criteria

1. THE system SHALL support between 1 and 50 Stair_Entities per Lower_Floor.
2. WHILE a floor is parked in `floorData`, THE 3D viewer SHALL render each of that floor's Stair_Entities vertically offset by that floor's `elevationCm` relative to the active floor's elevation.
3. WHEN the user switches the active floor, THE system SHALL preserve every Stair_Entity, with its geometry and position unchanged, on both the previously active (now parked) floor and the newly active floor.
4. WHEN the user undoes a stair creation, THE system SHALL remove the created Stair_Entity, re-fill the Stairwell_Void it cut, and restore the affected slabs to the exact state held before that creation.
5. WHEN the user redoes a previously undone stair creation, THE system SHALL restore the Stair_Entity and re-cut the Stairwell_Void to the exact state held immediately after the original creation.
6. IF the user requests an undo while the command history is empty, THEN THE system SHALL leave all Stair_Entities and slabs unchanged.
7. IF the user requests a redo while the redo history is empty, THEN THE system SHALL leave all Stair_Entities and slabs unchanged.
