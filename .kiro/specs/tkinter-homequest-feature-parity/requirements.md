# Requirements Document

## Introduction

The Python/Tkinter VastuCraft Pro editor already provides room and wall drawing, floor texture application, undo and redo, native JSON save and load, crash-safe autosave with rotating backups, configurable units, and a direct embedded Home Quest 3D viewer. The native layout schema remains centered on a single-floor `version: "1.0"` working set, and the Tkinter editor does not expose Home Quest's canonical multi-storey lifecycle, wall-finish painting, pillar, beam, deck/slab, or sun-position controls.

This feature plans parity for those missing capabilities while preserving the established integration flow: native Python layout data is validated and converted into existing Home Quest entities, stored with the existing Zustand semantics, and rendered by `SceneContent` and `FloorScene`. The feature does not introduce a second renderer or an intermediate `.hq.json` conversion format. The stale `EdgeChrome` screenshot error is a separate embedded-viewer compatibility bug and is outside this feature.

## Current Capability Baseline

- **Present in Tkinter**: room and wall geometry, room flooring textures, furniture, semantic windows, compass data, units and scale metadata, action-based undo and redo, JSON/YAML save and load, atomic local autosave, rotating backups, and direct request-ID delivery to the embedded viewer.
- **Present in Home Quest but missing from Tkinter**: canonical wall and floor finish identifiers, per-wall-face finishes, multiple storeys with elevations and parked per-floor geometry, pillar/beam/deck entities, and sun time/manual-direction state.
- **Parity constraint**: the Tkinter feature shall extend the native layout and bridge so the existing Home Quest import, store, migration, and rendering semantics remain authoritative.

## Glossary

- **Python_Editor**: The VastuCraft Pro Python/Tkinter 2D layout application.
- **Tkinter_Parity_Feature**: The planned feature set that adds the requested Home Quest capabilities to the Python_Editor.
- **Native_Layout**: A VastuCraft layout document produced and consumed by the Python_Editor.
- **Legacy_Native_Layout**: A valid native `version: "1.0"` single-floor document.
- **Extended_Native_Layout**: A versioned Native_Layout that can represent the parity data defined by this document.
- **Native_Serializer**: The Python_Editor component that saves and loads Native_Layout documents.
- **Canonical_Entity_Semantics**: The existing Home Quest entity meanings for floors, walls, rooms, pillars, beams, deck slabs, materials, and references.
- **Floor**: A storey with a unique identifier, display name, base elevation in centimeters, and isolated Floor_Geometry.
- **Ground_Floor**: The required lowest Floor with a base elevation of 0 centimeters.
- **Floor_Geometry**: The complete set of entities owned by one Floor, matching the existing Home Quest active-floor and parked-floor semantics.
- **Structural_Entity**: A Pillar, Beam, or Deck_Slab.
- **Pillar**: A canonical vertical structural member with position, footprint, height, elevation, shape, and material.
- **Beam**: A canonical horizontal structural member with endpoints, width, depth, elevation, and material.
- **Deck_Slab**: A canonical polygonal slab with thickness, elevation, type, and material.
- **Finish**: A canonical Home Quest material identifier and associated wall or floor category.
- **Paint_Tool**: The Python_Editor interaction for applying a compatible Finish to a wall face, wall, room floor, or Deck_Slab.
- **Sun_Settings**: Project viewer settings containing time of day, azimuth, and manual-direction override.
- **Cross_Floor_Reference**: An entity reference whose source and target belong to different Floors.
- **Import_Pipeline**: The existing Home Quest native-layout validation, conversion, and store-import flow.
- **Viewer_Pipeline**: The existing Home Quest `ViewerCanvas` → `SceneContent` → `FloorScene` rendering flow.
- **Embedded_Viewer**: The Home Quest 3D experience hosted directly inside the Python_Editor.
- **Reference_Parity_Project**: A valid project containing 5 Floors and no more than 2,000 total entities, including 200 Structural_Entities.
- **Reference_Windows_Environment**: Windows 10 or 11 with at least a 4-core 2.5 GHz processor, 8 GB RAM, SSD storage, and graphics support already accepted by the Embedded_Viewer.
- **Feature_Scope**: The product boundary established by this requirements document.
- **Floor_Manager**: The Python_Editor capability that creates, renames, activates, duplicates, elevates, and deletes Floors.
- **Material_Catalog**: The existing Home Quest registry of supported wall and floor Finishes.
- **History_Manager**: The existing Python_Editor action history extended to cover parity operations.
- **Autosave_Service**: The existing Python_Editor atomic local autosave and rotating-backup capability.
- **Parity_Validator**: The trust-boundary validation applied before parity data changes the current project or the Embedded_Viewer.
- **Viewer_Bridge**: The existing direct request-ID message channel between the Python_Editor and Embedded_Viewer.
- **Sun_Controller**: The Python_Editor controls and existing Home Quest sun computation that manage Sun_Settings.
- **Current_Project**: The complete in-memory Native_Layout currently open in the Python_Editor.

## Requirements
### Requirement 1: Architectural parity and reuse

**User Story:** As a maintainer, I want Tkinter parity to reuse Home Quest semantics, so that both applications describe and render one authoritative building model.

#### Acceptance Criteria

1. THE Tkinter_Parity_Feature SHALL represent Floors, Finishes, Pillars, Beams, Deck_Slabs, and Sun_Settings according to Canonical_Entity_Semantics.
2. WHEN the Python_Editor sends an Extended_Native_Layout for 3D display, THE Embedded_Viewer SHALL process the Extended_Native_Layout through the Import_Pipeline before replacing viewer state.
3. WHEN the Import_Pipeline accepts an Extended_Native_Layout, THE Viewer_Pipeline SHALL render the accepted canonical entities.
4. THE Viewer_Pipeline SHALL remain the exclusive 3D renderer for parity entities.
5. THE Native_Layout SHALL remain the Python_Editor's persisted source document without an intermediate `.hq.json` document.
6. THE Feature_Scope SHALL classify the stale `EdgeChrome` screenshot error as a separate bug outside the Tkinter_Parity_Feature.

### Requirement 2: Wall and floor finish application

**User Story:** As a home designer, I want to paint wall and floor surfaces in Tkinter, so that the 2D plan and Home Quest 3D view share the intended finishes.

#### Acceptance Criteria

1. WHEN the user selects a wall-compatible Finish and applies the Paint_Tool to a wall, THE Python_Editor SHALL assign the Finish identifier to the selected wall surface.
2. WHEN the user applies the Paint_Tool to a specific wall face, THE Python_Editor SHALL preserve the canonical side-A or side-B wall-face assignment.
3. WHEN a wall face has no face-specific Finish, THE Python_Editor SHALL use the wall's base Finish for that face.
4. WHEN the user selects a floor-compatible Finish and applies the Paint_Tool to a room floor, THE Python_Editor SHALL assign the Finish identifier to the selected room floor.
5. WHEN the user selects a floor-compatible Finish and applies the Paint_Tool to a Deck_Slab, THE Python_Editor SHALL assign the Finish identifier to the selected Deck_Slab.
6. IF the selected Finish category is incompatible with the selected surface, THEN THE Python_Editor SHALL preserve the existing surface Finish and display the required Finish category.
7. WHEN a surface Finish changes, THE Python_Editor SHALL display a 2D indication that distinguishes the applied Finish from the default Finish.
8. WHEN a Finish identifier is unavailable in the Material_Catalog, THE Import_Pipeline SHALL report the unavailable identifier and apply the existing canonical fallback behavior.

### Requirement 3: Ground floor and floor creation

**User Story:** As a home designer, I want a ground floor and additional storeys, so that I can model a multi-storey building.

#### Acceptance Criteria

1. WHEN the user creates a new project, THE Floor_Manager SHALL create exactly one Ground_Floor named `Ground Floor` at an elevation of 0 centimeters.
2. WHEN the user loads a Legacy_Native_Layout, THE Floor_Manager SHALL place all legacy geometry on one Ground_Floor at an elevation of 0 centimeters.
3. WHEN the user adds a Floor, THE Floor_Manager SHALL create an empty Floor with a unique identifier, a non-empty default name, and a base elevation above the highest existing Floor.
4. WHEN the Floor_Manager creates a Floor, THE Floor_Manager SHALL make the created Floor active.
5. THE Floor_Manager SHALL store Floor_Geometry separately for every Floor.
6. WHILE a Floor is active, THE Python_Editor SHALL limit 2D geometry creation, selection, and editing to the active Floor.

### Requirement 4: Floor naming, switching, and elevation

**User Story:** As a home designer, I want to identify and switch storeys and control elevations, so that each level is edited and stacked correctly.

#### Acceptance Criteria

1. WHEN the user renames a Floor with a non-empty name, THE Floor_Manager SHALL store the trimmed name for the selected Floor.
2. IF a Floor name contains no non-whitespace characters, THEN THE Floor_Manager SHALL preserve the previous Floor name and display a naming error.
3. WHEN the user activates another Floor, THE Floor_Manager SHALL park the outgoing Floor_Geometry and load the selected Floor_Geometry without changing either geometry set.
4. WHEN the user activates another Floor, THE Python_Editor SHALL clear selections that belong to the outgoing Floor.
5. WHEN the user changes a non-ground Floor elevation to a finite value greater than 0 centimeters and distinct from every other Floor elevation, THE Floor_Manager SHALL store the new elevation.
6. IF a Floor elevation is non-finite, negative, or equal to another Floor elevation, THEN THE Floor_Manager SHALL preserve the previous elevation and display the valid elevation constraints.
7. THE Floor_Manager SHALL preserve the Ground_Floor elevation at 0 centimeters.
8. WHEN a Floor elevation changes, THE Embedded_Viewer SHALL restack the affected Floor_Geometry at the stored elevation.

### Requirement 5: Floor duplication and deletion safeguards

**User Story:** As a home designer, I want to duplicate or remove storeys safely, so that repeated levels are efficient and project data is protected.

#### Acceptance Criteria

1. WHEN the user duplicates the active Floor, THE Floor_Manager SHALL create a new Floor above the highest existing Floor and copy the active Floor's canonical walls, rooms, openings, furniture, Pillars, Beams, Deck_Slabs, railings, and Finishes.
2. WHEN the Floor_Manager duplicates a Floor, THE Floor_Manager SHALL assign fresh identifiers and remap copied intra-floor references to the fresh identifiers.
3. WHEN the Floor_Manager duplicates a Floor, THE Floor_Manager SHALL omit stairs, roads, annotations, and Cross_Floor_References in accordance with the existing Home Quest floor-duplication semantics.
4. WHEN the Floor_Manager completes a Floor duplication, THE Floor_Manager SHALL make the duplicate Floor active.
5. IF the Current_Project contains exactly one Floor, THEN THE Floor_Manager SHALL preserve the Ground_Floor and disable Floor deletion.
6. WHEN the user requests deletion of a non-empty Floor, THE Floor_Manager SHALL require confirmation that reports the number of entities and affected Cross_Floor_References.
7. IF unresolved Cross_Floor_References target a Floor selected for deletion, THEN THE Floor_Manager SHALL preserve the Floor and identify every blocking reference.
8. WHEN the user confirms deletion of a Floor without blocking Cross_Floor_References, THE Floor_Manager SHALL delete the Floor_Geometry and activate the nearest remaining Floor by elevation.

### Requirement 6: Pillar lifecycle

**User Story:** As a home designer, I want to create and edit pillars, so that vertical structural supports appear consistently in 2D and 3D.

#### Acceptance Criteria

1. WHEN the user creates a Pillar, THE Python_Editor SHALL store a unique identifier, center position, width, depth, height, base elevation, rectangular or round shape, Finish identifier, and owning Floor identifier.
2. WHEN the user edits a Pillar with valid values, THE Python_Editor SHALL update the selected Pillar's position, dimensions, height, base elevation, shape, or Finish.
3. IF a Pillar width, depth, or height is non-finite or less than or equal to 0 centimeters, THEN THE Python_Editor SHALL preserve the previous Pillar and display the invalid field.
4. IF a Pillar base elevation is non-finite or less than 0 centimeters, THEN THE Python_Editor SHALL preserve the previous Pillar and display the valid elevation range.
5. WHEN the user deletes a Pillar without blocking references, THE Python_Editor SHALL remove the Pillar from the owning Floor_Geometry.
6. IF a Pillar has blocking entity references, THEN THE Python_Editor SHALL preserve the Pillar and identify the blocking references.

### Requirement 7: Beam lifecycle

**User Story:** As a home designer, I want to create and edit beams, so that horizontal structural members connect supports at controlled elevations.

#### Acceptance Criteria

1. WHEN the user creates a Beam, THE Python_Editor SHALL store a unique identifier, two endpoints, width, depth, elevation, Finish identifier, and owning Floor identifier.
2. WHEN the user edits a Beam with valid values, THE Python_Editor SHALL update the selected Beam's endpoints, width, depth, elevation, or Finish.
3. IF a Beam has coincident endpoints, THEN THE Python_Editor SHALL preserve the previous Floor_Geometry and display a non-zero-length requirement.
4. IF a Beam width or depth is non-finite or less than or equal to 0 centimeters, THEN THE Python_Editor SHALL preserve the previous Beam and display the invalid field.
5. IF a Beam elevation is non-finite or less than 0 centimeters, THEN THE Python_Editor SHALL preserve the previous Beam and display the valid elevation range.
6. WHEN the user deletes a Beam without blocking references, THE Python_Editor SHALL remove the Beam from the owning Floor_Geometry.
7. IF a Beam has blocking entity references, THEN THE Python_Editor SHALL preserve the Beam and identify the blocking references.

### Requirement 8: Deck and slab lifecycle

**User Story:** As a home designer, I want to create and edit deck slabs, so that balconies, corridors, landings, roofs, and custom slabs appear in the building model.

#### Acceptance Criteria

1. WHEN the user creates a Deck_Slab, THE Python_Editor SHALL store a unique identifier, polygon, thickness, elevation, canonical type, Finish identifier, and owning Floor identifier.
2. WHEN the user edits a Deck_Slab with valid values, THE Python_Editor SHALL update the selected Deck_Slab's polygon, thickness, elevation, type, or Finish.
3. IF a Deck_Slab polygon has fewer than 3 distinct vertices or has zero area, THEN THE Python_Editor SHALL preserve the previous Floor_Geometry and display the polygon constraint.
4. IF a Deck_Slab polygon self-intersects, THEN THE Python_Editor SHALL preserve the previous Floor_Geometry and identify the intersecting edges.
5. IF a Deck_Slab thickness is non-finite or less than or equal to 0 centimeters, THEN THE Python_Editor SHALL preserve the previous Deck_Slab and display the invalid field.
6. IF a Deck_Slab elevation is non-finite or less than 0 centimeters, THEN THE Python_Editor SHALL preserve the previous Deck_Slab and display the valid elevation range.
7. WHEN the user deletes a Deck_Slab without blocking references, THE Python_Editor SHALL remove the Deck_Slab from the owning Floor_Geometry.
8. IF a Deck_Slab has blocking entity references, THEN THE Python_Editor SHALL preserve the Deck_Slab and identify the blocking references.

### Requirement 9: Sun positioning controls

**User Story:** As a home designer, I want to control time and sun direction from Tkinter, so that daylight in the embedded 3D view matches the intended study.

#### Acceptance Criteria

1. THE Sun_Controller SHALL provide a time-of-day value from 0 through 24 hours, an azimuth value from 0 through less than 360 degrees, and a manual-direction override.
2. WHEN the user changes time of day while manual-direction override is disabled, THE Sun_Controller SHALL use the existing Home Quest day-arc computation to derive solar elevation and azimuth.
3. WHEN the user enables manual-direction override, THE Sun_Controller SHALL use the stored azimuth as clockwise degrees from project north.
4. WHEN the user changes the manual azimuth, THE Sun_Controller SHALL normalize the value into the range from 0 through less than 360 degrees.
5. WHEN Sun_Settings change, THE Embedded_Viewer SHALL update lighting, shadows, sky state, clock label, and compass-direction label from the existing Home Quest sun computation.
6. WHEN the user loads an Extended_Native_Layout containing Sun_Settings, THE Sun_Controller SHALL restore the saved time, azimuth, and manual-direction override.
7. WHEN the user loads a Native_Layout without Sun_Settings, THE Sun_Controller SHALL use 12:00, 120 degrees, and disabled manual-direction override.

### Requirement 10: Native schema evolution and backward compatibility

**User Story:** As a designer, I want old and new native layouts to remain usable, so that parity does not strand existing projects.

#### Acceptance Criteria

1. THE Extended_Native_Layout SHALL declare a schema version distinct from `1.0` and contain versioned representations for Floors, per-floor geometry, Finishes, Structural_Entities, Sun_Settings, and Cross_Floor_References.
2. WHEN the Native_Serializer loads a Legacy_Native_Layout, THE Native_Serializer SHALL preserve supported legacy rooms, shapes, furniture, windows, text, flooring, compass, units, scale, grid, and zoom data.
3. WHEN the Native_Serializer loads a supported older Native_Layout, THE Native_Serializer SHALL migrate the document in memory to the current Extended_Native_Layout without modifying the source file.
4. WHEN the Native_Serializer saves a migrated project, THE Native_Serializer SHALL write the current Extended_Native_Layout version.
5. WHEN an Extended_Native_Layout is saved and reloaded, THE Native_Serializer SHALL reproduce equivalent Floors, Floor_Geometry, Finishes, Structural_Entities, Sun_Settings, units, and references.
6. IF a Native_Layout declares a newer unsupported version, THEN THE Native_Serializer SHALL reject the document before changing the Current_Project and display the supported version range.
7. IF an optional parity collection is absent from a supported Native_Layout, THEN THE Native_Serializer SHALL initialize the collection with the version-defined default.
8. WHEN Home Quest imports a supported Native_Layout version, THE Import_Pipeline SHALL preserve the same canonical geometry, material, elevation, and reference meanings used by Home Quest `.hq.json` projects.
9. THE Import_Pipeline SHALL continue to distinguish Native_Layout documents from Home Quest `.hq.json` documents.

### Requirement 11: Undo and redo coverage

**User Story:** As a home designer, I want parity operations to support undo and redo, so that design changes remain reversible.

#### Acceptance Criteria

1. WHEN the user completes a Finish application, Floor lifecycle operation, Structural_Entity lifecycle operation, elevation change, or Sun_Settings change, THE History_Manager SHALL record one atomic undoable action.
2. WHEN the user invokes undo, THE History_Manager SHALL restore the complete pre-action state, including affected identifiers and references.
3. WHEN the user invokes redo, THE History_Manager SHALL restore the complete post-action state, including affected identifiers and references.
4. WHEN the user performs a new mutation after undo, THE History_Manager SHALL clear the redo sequence.
5. WHEN the user switches Floors, THE History_Manager SHALL retain action-to-Floor ownership and prevent an action from changing the wrong Floor_Geometry.
6. WHEN undo or redo changes viewer-visible state, THE Viewer_Bridge SHALL synchronize the restored Current_Project with the Embedded_Viewer.
7. WHILE no undo or redo action is available, THE Python_Editor SHALL present the corresponding history command as unavailable.

### Requirement 12: Save, load, and autosave integrity

**User Story:** As a home designer, I want every parity feature persisted by existing project workflows, so that work survives restarts and failures.

#### Acceptance Criteria

1. WHEN the user saves the Current_Project, THE Native_Serializer SHALL persist every Floor, Floor_Geometry, Finish, Structural_Entity, Sun_Settings value, unit setting, and valid reference.
2. WHEN a manual save succeeds, THE Native_Serializer SHALL replace the target document with a complete valid Extended_Native_Layout.
3. IF a manual save fails, THEN THE Native_Serializer SHALL preserve the previous target document and display the failure reason.
4. WHEN the user loads a Native_Layout, THE Parity_Validator SHALL complete schema, value, geometry, and reference validation before replacing the Current_Project.
5. IF Native_Layout validation or migration fails, THEN THE Python_Editor SHALL retain the Current_Project and display the failing path and reason.
6. WHEN an undoable parity action is recorded, THE Autosave_Service SHALL schedule an atomic autosave through the existing action-logger integration.
7. WHEN the Autosave_Service writes a parity project, THE Autosave_Service SHALL include every Floor and project-level Sun_Settings in the autosave and rotating backup.
8. WHEN the user restores a valid autosave or backup, THE Native_Serializer SHALL restore parity data with the same behavior as manual load.

### Requirement 13: Units and numeric interpretation

**User Story:** As a home designer, I want parity dimensions to respect the selected units, so that structural and elevation values remain accurate.

#### Acceptance Criteria

1. THE Python_Editor SHALL store canonical Floor elevations, Pillar dimensions, Beam dimensions, Deck_Slab dimensions, and Home Quest geometry in centimeters at the Import_Pipeline boundary.
2. WHEN the user enters a parity dimension in the selected display unit, THE Python_Editor SHALL convert the value through the existing unit, unit-scale, grid-spacing, and zoom contract.
3. WHEN the user changes the display unit, THE Python_Editor SHALL preserve canonical geometry and update displayed parity values to the selected unit.
4. WHEN the Python_Editor serializes canvas coordinates, THE Native_Serializer SHALL preserve the existing Y-reflection and origin-normalization contract used by the Import_Pipeline.
5. IF a numeric field contains a non-finite or non-numeric value, THEN THE Python_Editor SHALL preserve the previous value and identify the invalid field.

### Requirement 14: Validation and cross-floor reference integrity

**User Story:** As a maintainer, I want parity data validated at every trust boundary, so that malformed projects cannot corrupt editor or viewer state.

#### Acceptance Criteria

1. WHEN the Python_Editor loads or transmits a Native_Layout, THE Parity_Validator SHALL validate schema version, collection limits, identifiers, finite numbers, coordinate limits, polygon validity, material identifiers, and serialized size.
2. THE Parity_Validator SHALL require every entity identifier to be unique across the Current_Project.
3. THE Parity_Validator SHALL require every intra-floor reference to resolve to an entity in the owning Floor_Geometry.
4. THE Parity_Validator SHALL require every Cross_Floor_Reference to identify an existing source Floor, target Floor, source entity, and target entity.
5. IF a reference is missing, cyclic where cycles are unsupported, or type-incompatible, THEN THE Parity_Validator SHALL reject the affected operation and report the reference path.
6. IF validation fails during viewer synchronization, THEN THE Embedded_Viewer SHALL retain the last successfully rendered project.
7. WHEN the user moves or duplicates an entity, THE Python_Editor SHALL preserve valid references or report the references that block the operation.

### Requirement 15: Direct embedded-viewer synchronization

**User Story:** As a home designer, I want the embedded 3D view to follow Tkinter changes, so that every floor and structural edit is visible without file exchange.

#### Acceptance Criteria

1. WHEN the user opens the Embedded_Viewer, THE Viewer_Bridge SHALL send the latest complete Current_Project directly from the Native_Serializer.
2. WHILE the Embedded_Viewer is active, WHEN an undoable parity action completes, THE Viewer_Bridge SHALL send the newest complete valid Current_Project within 250 milliseconds without writing an intermediate file.
3. WHEN the Viewer_Bridge sends a project update, THE Viewer_Bridge SHALL assign a monotonically increasing request identifier.
4. IF project updates complete out of order, THEN THE Embedded_Viewer SHALL apply the newest successful request and discard older requests.
5. WHEN the Import_Pipeline accepts a project update, THE Embedded_Viewer SHALL atomically display all Floors at stored elevations with accepted Finishes and Structural_Entities.
6. WHEN Sun_Settings change while the Embedded_Viewer is active, THE Viewer_Bridge SHALL send the newest Sun_Settings without requiring a layout file save or tab reactivation.
7. WHEN the user activates a Floor in 2D, THE Embedded_Viewer SHALL preserve the whole-building 3D stack and identify the active Floor through existing viewer semantics.
8. IF the Viewer_Bridge cannot deliver an update, THEN THE Python_Editor SHALL preserve editable 2D state and display a retryable synchronization error.

### Requirement 16: Error handling and recovery

**User Story:** As a home designer, I want actionable errors without data loss, so that I can correct a project and continue working.

#### Acceptance Criteria

1. IF a parity creation or edit operation fails validation, THEN THE Python_Editor SHALL preserve the pre-operation Current_Project and display the entity type, field, and constraint.
2. IF Native_Layout parsing fails, THEN THE Native_Serializer SHALL preserve the Current_Project and display the document location available from the parser.
3. IF the Embedded_Viewer rejects an Extended_Native_Layout, THEN THE Embedded_Viewer SHALL retain the last successful scene and display the import failure reason.
4. IF the embedded rendering process stops, THEN THE Python_Editor SHALL keep 2D editing, save, load, autosave, undo, and redo available and present the existing viewer retry action.
5. WHEN a retry succeeds, THE Viewer_Bridge SHALL resend the newest complete valid Current_Project and Sun_Settings.
6. IF an unavailable Finish or unsupported optional entity is encountered during import, THEN THE Import_Pipeline SHALL report the source identifier without silently substituting a different semantic entity.

### Requirement 17: Responsiveness and capacity

**User Story:** As a home designer, I want parity operations to remain responsive on realistic projects, so that multi-storey editing stays practical.

#### Acceptance Criteria

1. WHEN the user switches Floors in a Reference_Parity_Project on a Reference_Windows_Environment, THE Python_Editor SHALL display the selected Floor_Geometry within 500 milliseconds.
2. WHEN the user duplicates a Floor containing 400 entities on a Reference_Windows_Environment, THE Floor_Manager SHALL complete duplication within 2 seconds while keeping the Tk event loop responsive.
3. WHEN the Native_Serializer saves or loads a Reference_Parity_Project on a Reference_Windows_Environment, THE Native_Serializer SHALL complete the operation within 3 seconds while keeping the Tk event loop responsive.
4. WHEN the Viewer_Bridge sends a Reference_Parity_Project, THE Python_Editor SHALL remain responsive until the Embedded_Viewer reports success or failure.
5. WHEN the user performs 20 consecutive Floor switches, THE Floor_Manager SHALL preserve the entity count, identifiers, geometry values, and references of every unedited Floor.
6. WHEN the user performs 20 consecutive Plan-to-Viewer tab switches, THE Embedded_Viewer SHALL reuse one viewer runtime without accumulating browser or server instances.

### Requirement 18: Compatibility and scope boundaries

**User Story:** As a product owner, I want explicit boundaries for the parity release, so that the plan addresses the requested gaps without unrelated expansion.

#### Acceptance Criteria

1. THE Feature_Scope SHALL include wall and floor Finishes, Floor lifecycle management, Pillars, Beams, Deck_Slabs, Sun_Settings, schema evolution, persistence, history, validation, and direct viewer synchronization.
2. THE Feature_Scope SHALL preserve existing Tkinter room, wall, furniture, window, flooring, compass, unit, save, load, autosave, and viewer workflows.
3. THE Feature_Scope SHALL preserve the existing Home Quest file import workflow and Canonical_Entity_Semantics.
4. THE Feature_Scope SHALL defer new Tkinter authoring tools for stairs, railings, roads, cloud collaboration, and renderer replacement to separately approved features.
5. THE Feature_Scope SHALL defer remediation of the stale `EdgeChrome` screenshot error to a separate bug-fix workflow.
6. THE Feature_Scope SHALL target the existing supported Windows Python/Tkinter environment.
