import React from 'react';
import { EditorCanvas } from './EditorCanvas';
import { RoomAssignmentPanel } from './RoomAssignmentPanel';
import { useRoomDetection } from '../hooks/useRoomDetection';
import { useVastuAnalysis } from '@/domains/vastu/hooks/useVastuAnalysis';

export const EditorScreen: React.FC = () => {
  // This automatically runs room detection whenever walls/vertices change
  useRoomDetection();
  useVastuAnalysis();

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <EditorCanvas />
      <RoomAssignmentPanel />
    </div>
  );
};
