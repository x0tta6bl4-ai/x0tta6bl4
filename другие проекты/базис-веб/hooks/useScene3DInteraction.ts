import { useCallback, useRef, useEffect, type RefObject, type PointerEvent as ReactPointerEvent } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

interface UseScene3DInteractionProps {
  renderer: THREE.WebGLRenderer | null;
  camera: THREE.PerspectiveCamera | null;
  orbitControls: OrbitControls | null;
  trackballControls: TrackballControls | null;
  transformControls: TransformControls | null;
  panelsGroup: THREE.Group | null;
  containerRef: RefObject<HTMLDivElement>;
  selectPanel: (id: string | null, multi?: boolean) => void;
}

export const useScene3DInteraction = ({
  renderer,
  camera,
  orbitControls,
  trackballControls,
  transformControls,
  panelsGroup,
  containerRef,
  selectPanel,
}: UseScene3DInteractionProps) => {
  const isCubeDragging = useRef(false);
  const prevCubeMouse = useRef({ x: 0, y: 0 });

  const handleCubeMove = useCallback(
    (e: PointerEvent) => {
      if (!isCubeDragging.current || !orbitControls || !camera) return;
      e.preventDefault();
      const deltaX = e.clientX - prevCubeMouse.current.x;
      const deltaY = e.clientY - prevCubeMouse.current.y;
      const offset = new THREE.Vector3().copy(camera.position).sub(orbitControls.target);
      const spherical = new THREE.Spherical().setFromVector3(offset);
      spherical.theta -= deltaX * 0.005;
      spherical.phi -= deltaY * 0.005;
      spherical.phi = Math.max(0.01, Math.min(Math.PI - 0.01, spherical.phi));
      offset.setFromSpherical(spherical);
      camera.position.copy(orbitControls.target).add(offset);
      camera.lookAt(orbitControls.target);
      orbitControls.update();
      prevCubeMouse.current = { x: e.clientX, y: e.clientY };
    },
    [orbitControls, camera]
  );

  const handleCubeUp = useCallback(() => {
    isCubeDragging.current = false;
    window.removeEventListener('pointermove', handleCubeMove);
    window.removeEventListener('pointerup', handleCubeUp);
    document.body.style.cursor = '';
  }, [handleCubeMove]);

  const handleCubeDown = useCallback(
    (e: ReactPointerEvent) => {
      e.preventDefault();
      e.stopPropagation();
      isCubeDragging.current = true;
      prevCubeMouse.current = { x: e.clientX, y: e.clientY };
      window.addEventListener('pointermove', handleCubeMove);
      window.addEventListener('pointerup', handleCubeUp);
      document.body.style.cursor = 'grabbing';
    },
    [handleCubeMove, handleCubeUp]
  );

  const handlePanelSelection = useCallback(
    (e: PointerEvent) => {
      if (!containerRef.current || !camera || !panelsGroup) return;

      const target = e.target as HTMLElement;
      if (target.closest('.cube-face') || target.closest('button')) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(new THREE.Vector2(x, y), camera);
      const intersects = raycaster.intersectObjects(panelsGroup.children, false);

      if (intersects.length > 0) {
        const hit = intersects.find(i => i.object instanceof THREE.InstancedMesh && i.object.userData.isPanel);
        if (hit && hit.instanceId !== undefined) {
          const pid = hit.object.userData.panelMap[hit.instanceId];
          if (pid) {
            selectPanel(pid, e.ctrlKey || e.shiftKey);
            return;
          }
        }
      }
      if (!e.ctrlKey && !e.shiftKey) selectPanel(null);
    },
    [containerRef, camera, panelsGroup, selectPanel]
  );

  useEffect(() => {
    if (!renderer) return;
    const dom = renderer.domElement;
    dom.addEventListener('pointerup', handlePanelSelection);
    (window as any).handleCubeDown = handleCubeDown;

    return () => {
      dom.removeEventListener('pointerup', handlePanelSelection);
      (window as any).handleCubeDown = null;
    };
  }, [renderer, handlePanelSelection, handleCubeDown]);

  return { handleCubeDown };
};
