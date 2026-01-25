import { useCallback, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';

interface UseScene3DCameraProps {
  camera: THREE.PerspectiveCamera | null;
  orbitControls: OrbitControls | null;
  trackballControls: TrackballControls | null;
  panelsGroup: THREE.Group | null;
}

export const useScene3DCamera = ({
  camera,
  orbitControls,
  trackballControls,
  panelsGroup,
}: UseScene3DCameraProps) => {
  const isInitializedRef = useRef(false);

  const smoothViewTransition = useCallback(
    (targetPos: THREE.Vector3, targetLookAt: THREE.Vector3) => {
      if (!camera || !orbitControls || !trackballControls) return;

      const startPos = camera.position.clone();
      const startLookAt = orbitControls.target.clone();
      const startTime = Date.now();
      const duration = 600;

      const animateTransition = () => {
        const now = Date.now();
        const progress = Math.min((now - startTime) / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 3);

        camera.position.lerpVectors(startPos, targetPos, ease);
        orbitControls.target.lerpVectors(startLookAt, targetLookAt, ease);
        trackballControls.target.lerpVectors(startLookAt, targetLookAt, ease);

        orbitControls.update();
        trackballControls.update();

        if (progress < 1) {
          requestAnimationFrame(animateTransition);
        }
      };
      animateTransition();
    },
    [camera, orbitControls, trackballControls]
  );

  const setView = useCallback(
    (view: 'front' | 'back' | 'left' | 'right' | 'top' | 'bottom') => {
      if (!panelsGroup) return;

      const box = new THREE.Box3().setFromObject(panelsGroup);
      const center = box.isEmpty() ? new THREE.Vector3(0, 0, 0) : box.getCenter(new THREE.Vector3());
      const size = box.isEmpty() ? new THREE.Vector3(1000, 1000, 1000) : box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);
      const dist = Math.max(maxDim * 2.0, 2000);

      const targetPos = new THREE.Vector3();

      switch (view) {
        case 'front':
          targetPos.set(center.x, center.y, center.z + dist);
          break;
        case 'back':
          targetPos.set(center.x, center.y, center.z - dist);
          break;
        case 'right':
          targetPos.set(center.x + dist, center.y, center.z);
          break;
        case 'left':
          targetPos.set(center.x - dist, center.y, center.z);
          break;
        case 'top':
          targetPos.set(center.x, center.y + dist, center.z + 0.1);
          break;
        case 'bottom':
          targetPos.set(center.x, center.y - dist, center.z + 0.1);
          break;
      }

      smoothViewTransition(targetPos, center);
    },
    [panelsGroup, smoothViewTransition]
  );

  const fitCameraToScene = useCallback(() => {
    if (!panelsGroup) return;
    const box = new THREE.Box3().setFromObject(panelsGroup);
    if (box.isEmpty()) return;

    const center = new THREE.Vector3();
    box.getCenter(center);
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);

    if (trackballControls) {
      trackballControls.minDistance = Math.max(10, maxDim * 0.1);
      trackballControls.maxDistance = Math.max(50000, maxDim * 15);
    }

    if (!isInitializedRef.current) {
      const distance = Math.max(2000, maxDim * 2.5);
      const targetPos = new THREE.Vector3(center.x + distance, center.y + distance * 0.5, center.z + distance);
      smoothViewTransition(targetPos, center);
      isInitializedRef.current = true;
    }
  }, [panelsGroup, trackballControls, smoothViewTransition]);

  return { smoothViewTransition, setView, fitCameraToScene };
};
