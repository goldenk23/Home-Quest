# Requirements Document

## Introduction

VastuCraft Pro currently creates a native Python layout JSON that Home Quest can import and render in 3D. This feature brings that same Home Quest 3D experience into the Python/Tkinter application so a designer can switch from the working 2D plan to an in-app 3D preview without manually saving, importing, or opening another application.

The integration shall reuse the existing native serializer, validation/conversion pipeline, Zustand entities, and React Three Fiber renderer. It shall not introduce a second renderer or an intermediate `.hq.json` format.

## Glossary

- **Python_Editor**: The VastuCraft Pro Python/Tkinter 2D layout application.
- **Native_Layout**: The `version: "1.0"` object returned by `LayoutSerializer.serialize_layout()`.
- **Embedded_Viewer**: The Home Quest 3D experience hosted inside the Python_Editor.
- **Viewer_Tab**: The content-level tab that displays the Embedded_Viewer.
- **Plan_Tab**: The content-level tab that displays the existing 2D canvas.
- **Import_Pipeline**: `assertVastuLayout` followed by `convertVastuLayout` and `importVastuLayout`.
- **Viewer_Pipeline**: `ViewerCanvas` followed by `SceneContent` and `FloorScene`.
- **Walkthrough_Mode**: The existing Home Quest first-person camera and collision behavior.
- **Orbit_Mode**: The existing Home Quest orbit camera behavior.
- **Viewer_Runtime**: The packaged web assets and embedded browser engine used by the Embedded_Viewer.

## Requirements

### Requirement 1: In-app 2D and 3D workspace

**User Story:** As a home designer, I want a 3D tab inside VastuCraft Pro, so that I can inspect my house without leaving the application.

#### Acceptance Criteria

1. THE Python_Editor SHALL provide a Plan_Tab and a Viewer_Tab in the expandable main content area while preserving the existing drawing sidebar and top actions.
2. WHEN the user selects the Viewer_Tab or invokes a View in 3D action, THE Python_Editor SHALL display the Embedded_Viewer inside its own window rather than opening an external browser or separate application window.
3. WHEN the user selects the Plan_Tab, THE Python_Editor SHALL restore the existing 2D canvas with its current layout, selection, zoom, and editing state unchanged.
4. WHILE the Viewer_Tab is active, THE Embedded_Viewer SHALL resize with the Python_Editor content area without requiring a page reload.

### Requirement 2: Reuse of the established conversion and rendering flow

**User Story:** As a designer, I want the embedded preview to match Home Quest, so that both applications show the same house.

#### Acceptance Criteria

1. WHEN a 3D preview is requested, THE Python_Editor SHALL obtain the Native_Layout from `LayoutSerializer.serialize_layout()` without displaying a save dialog.
2. WHEN the Embedded_Viewer receives a Native_Layout, THE system SHALL process it through the Import_Pipeline before changing viewer state.
3. WHEN import succeeds, THE Embedded_Viewer SHALL render the imported entities through the Viewer_Pipeline.
4. THE system SHALL NOT create a second 3D renderer or convert the Native_Layout through an `.hq.json` file.
5. WHEN furniture cannot be mapped, THE Import_Pipeline SHALL omit it from 3D and report its native name without substituting another object.
### Requirement 3: Preview synchronization

**User Story:** As a designer, I want the 3D view to reflect my latest 2D work, so that I can evaluate each revision.

#### Acceptance Criteria

1. WHEN the user activates the Viewer_Tab, THE Python_Editor SHALL serialize and send the current Native_Layout to the Embedded_Viewer.
2. WHEN the user invokes Refresh 3D, THE Python_Editor SHALL serialize and send the current Native_Layout again without requiring a file save or file picker.
3. WHEN a refreshed Native_Layout imports successfully, THE Embedded_Viewer SHALL atomically replace its previous plan and reset the camera to frame the refreshed plan.
4. IF validation or conversion fails, THEN THE Embedded_Viewer SHALL retain the last successfully rendered plan and display the failure reason.
5. THE first release SHALL NOT require continuous synchronization while the Plan_Tab is active; activation and explicit refresh SHALL be the synchronization points.

### Requirement 4: Orbit and walkthrough facilities

**User Story:** As a designer, I want the same orbit and walking controls as Home Quest, so that I can inspect the building from outside and inside.

#### Acceptance Criteria

1. THE Viewer_Tab SHALL provide controls for Orbit_Mode, Walkthrough_Mode, camera reset, and render quality.
2. WHILE Orbit_Mode is active, THE Embedded_Viewer SHALL use the existing Home Quest orbit controls, plan-centroid targeting, distance limits, and above-ground camera limits.
3. WHEN the user selects Walkthrough_Mode and clicks the 3D canvas, THE Embedded_Viewer SHALL request pointer lock and accept the existing mouse, WASD, arrow-key, Shift, and Escape controls.
4. WHILE Walkthrough_Mode is active, THE Embedded_Viewer SHALL use the existing room spawn, wall/opening collision, floor selection, and stair traversal behavior.
5. WHEN the user leaves the Viewer_Tab, THE Embedded_Viewer SHALL release pointer lock and stop active movement input.
6. WHEN pointer lock or keyboard focus is unavailable, THE Viewer_Tab SHALL present a clear instruction or error instead of silently disabling walkthrough.

### Requirement 5: Viewer-only embedded experience

**User Story:** As a designer, I want a focused preview, so that Home Quest editor controls do not clutter the Python application.

#### Acceptance Criteria

1. THE Embedded_Viewer SHALL load a viewer-only interface containing the 3D canvas, preview status, and required camera/quality controls.
2. THE Embedded_Viewer SHALL NOT mount the Home Quest 2D editor, browser plan replacement confirmation, backup scheduler, or full SandboxView tool panels.
3. WHEN the Native_Layout imports successfully, THE Viewer_Tab SHALL report imported room, wall, opening, and furniture counts plus unmapped or residual warnings.
4. WHILE no valid plan with walls has been loaded, THE Viewer_Tab SHALL display an empty-state explanation rather than a blank canvas.

### Requirement 6: Self-contained production runtime

**User Story:** As a user, I want the 3D preview to work with the installed desktop application, so that I do not need to run Home Quest or Node.js separately.

#### Acceptance Criteria

1. THE production Python_Editor SHALL start and stop the Viewer_Runtime as part of its own lifecycle.
2. THE production Viewer_Runtime SHALL load packaged Home Quest build assets, models, textures, and manifests without requiring Node.js, a Vite development server, internet access, or the standalone Home Quest application.
3. THE Viewer_Runtime SHALL serve packaged web assets only through a loopback interface and SHALL NOT listen on external network interfaces.
4. WHEN the Python_Editor closes, THE system SHALL stop its local asset server, release the embedded browser, and terminate viewer-related background resources.
5. IF required build assets or browser runtime support are unavailable, THEN THE Python_Editor SHALL keep the Plan_Tab usable and display an actionable Viewer_Tab error.
### Requirement 7: Trust-boundary validation and transport

**User Story:** As a user, I want malformed layouts to be handled safely, so that previewing cannot corrupt my work or expose my machine.

#### Acceptance Criteria

1. THE Embedded_Viewer SHALL treat every Native_Layout received from the Python host as untrusted input and complete `assertVastuLayout` validation before store replacement.
2. THE Embedded_Viewer SHALL enforce the existing entity, geometry-point, finite-number, coordinate, schema-version, and layout-size limits.
3. THE Python_Editor SHALL transfer the Native_Layout directly to its own Embedded_Viewer without writing an intermediate conversion file or exposing a writable public HTTP endpoint.
4. WHEN a transport message is not a supported layout command, THE Embedded_Viewer SHALL ignore it without changing viewer state.
5. IF a layout message exceeds the supported size, THEN THE system SHALL reject it and retain the last successfully rendered plan.

### Requirement 8: Responsiveness and lifecycle stability

**User Story:** As a designer, I want switching views to remain reliable, so that repeated previews do not freeze or leak resources.

#### Acceptance Criteria

1. WHEN the user switches between Plan_Tab and Viewer_Tab at least 20 consecutive times, THE Python_Editor SHALL retain one viewer instance and SHALL NOT create accumulating browser or server instances.
2. WHILE a preview is loading or converting, THE Viewer_Tab SHALL display progress and keep the Python_Editor event loop responsive.
3. IF the user requests another refresh while one is pending, THEN THE system SHALL render the newest complete Native_Layout and SHALL NOT replace it afterward with an older request.
4. WHEN the embedded browser reports a rendering-process failure, THE Viewer_Tab SHALL provide a retry action without requiring the Python_Editor to restart.
5. THE Embedded_Viewer SHALL continue to apply the existing heavy-scene and render-quality behavior of `ViewerCanvas`.

### Requirement 9: Compatibility and scope boundaries

**User Story:** As a maintainer, I want the embedded path to preserve current import behavior, so that the existing file-based workflow remains dependable.

#### Acceptance Criteria

1. THE existing Import Python Layout file workflow in Home Quest SHALL continue to accept the same Native_Layout format and produce the same conversion report.
2. THE existing Python save, autosave, and load workflows SHALL continue to operate independently of the Viewer_Tab.
3. THE embedded bridge SHALL preview the single-floor geometry represented by native schema version 1.0 and SHALL NOT fabricate stairs, pillars, beams, roads, deck slabs, railings, or additional floors absent from that schema.
4. WHEN the Native_Layout includes coordinates and metadata, THE Import_Pipeline SHALL preserve the existing unit, unit-scale, grid-spacing, zoom, Y-reflection, and origin-normalization contract.
5. THE first production target SHALL be the existing Windows Python/Tkinter environment; support for other desktop platforms is outside this feature unless separately specified.
