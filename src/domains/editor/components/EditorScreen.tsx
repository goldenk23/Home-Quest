import React from 'react';
import { EditorCanvas } from './EditorCanvas';
import { RoomAssignmentPanel } from './RoomAssignmentPanel';
import { useRoomDetection } from '../hooks/useRoomDetection';
import { useKeyboardEditor } from '../hooks/useKeyboardEditor';
import { useVastuAnalysis } from '@/domains/vastu/hooks/useVastuAnalysis';
import { useKeyboardShortcuts } from '@/app/hooks/useKeyboardShortcuts';
import { ScreenReaderAnnouncer } from '@/domains/shared/components/ScreenReaderAnnouncer';

export const EditorScreen: React.FC = () => {
  // Engine hooks (render nothing, keep the model + interactions live):
  useRoomDetection();        // keeps rooms in sync with walls
  useVastuAnalysis();        // keeps plan boundary + Vastu score in sync
  useKeyboardEditor();       // arrow-key nudging / Delete on the selection
  useKeyboardShortcuts();    // Ctrl/Cmd+Z undo, Ctrl+Y / Ctrl+Shift+Z redo

  return (
    <div id="editor-canvas" style={{ width: '100%', height: '100%', position: 'relative' }}>
      <ScreenReaderAnnouncer />
      <EditorCanvas />
      <RoomAssignmentPanel />
    </div>
  );
};
