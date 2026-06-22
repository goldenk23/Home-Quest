import React from 'react';
import { EditorCanvas } from './EditorCanvas';
import { useRoomDetection } from '../hooks/useRoomDetection';

export const EditorScreen: React.FC = () => {
  // This automatically runs room detection whenever walls/vertices change
  useRoomDetection();

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <EditorCanvas />
    </div>
  );
};
