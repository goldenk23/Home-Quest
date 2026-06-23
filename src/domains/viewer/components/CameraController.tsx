// src/domains/viewer/components/CameraController.tsx

import React from 'react';
import { OrbitCameraController } from '../hooks/useOrbitCamera';
import { useFirstPersonControls } from '../hooks/useFirstPerson';

interface CameraControllerProps {
  mode: 'orbit' | 'firstPerson';
}

export const CameraController: React.FC<CameraControllerProps> = ({ mode }) => {
  return mode === 'orbit' ? <OrbitCameraController /> : <FirstPersonCamera />;
};

/**
 * First-person controls. Pointer-lock is requested via a DOM click handler on the canvas
 * (registered inside useFirstPersonControls), so a click anywhere on the 3D view reliably
 * starts the walkthrough — no fragile world-space click-catcher needed.
 */
const FirstPersonCamera: React.FC = () => {
  useFirstPersonControls();
  return null;
};
