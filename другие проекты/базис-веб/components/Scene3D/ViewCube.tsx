import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';

interface ViewCubeProps {
  camera: THREE.PerspectiveCamera | null;
  onViewChange: (view: 'front' | 'back' | 'left' | 'right' | 'top' | 'bottom') => void;
  onPointerDown: (e: React.PointerEvent) => void;
}

const ViewCube: React.FC<ViewCubeProps> = ({ camera, onViewChange, onPointerDown }) => {
  const cubeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!camera || !cubeRef.current) return;

    const updateCubeRotation = () => {
      const vector = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
      const theta = Math.atan2(vector.x, vector.z);
      const phi = Math.atan2(Math.sqrt(vector.x * vector.x + vector.z * vector.z), vector.y);
      const rotX = (phi - Math.PI / 2) * (180 / Math.PI);
      const rotY = theta * (180 / Math.PI) + 180;
      cubeRef.current!.style.transform = `rotateX(${-rotX}deg) rotateY(${-rotY}deg)`;
    };

    const rafId = requestAnimationFrame(updateCubeRotation);
    return () => cancelAnimationFrame(rafId);
  }, [camera]);

  return (
    <div className="scene-container hidden sm:block" onPointerDown={onPointerDown}>
      <div ref={cubeRef} className="cube">
        <div className="cube-face cube__front" onClick={() => onViewChange('front')}>
          Front
        </div>
        <div className="cube-face cube__back" onClick={() => onViewChange('back')}>
          Back
        </div>
        <div className="cube-face cube__right" onClick={() => onViewChange('right')}>
          Right
        </div>
        <div className="cube-face cube__left" onClick={() => onViewChange('left')}>
          Left
        </div>
        <div className="cube-face cube__top" onClick={() => onViewChange('top')}>
          Top
        </div>
        <div className="cube-face cube__bottom" onClick={() => onViewChange('bottom')}>
          Bottom
        </div>
      </div>
    </div>
  );
};

export default ViewCube;
