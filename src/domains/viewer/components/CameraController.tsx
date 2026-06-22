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

/** An invisible click-catcher that enters pointer-lock when clicked. */
const FirstPersonCamera: React.FC = () => {
  const { requestLock } = useFirstPersonControls();
  return (
    <mesh visible={false} onClick={requestLock}>
      <planeGeometry args={[1000, 1000]} />
    </mesh>
  );
};
