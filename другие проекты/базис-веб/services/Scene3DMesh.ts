import * as THREE from 'three';
import { Panel, Axis } from '../types';
import { Scene3DMaterialManager } from './Scene3DMaterial';

// Кэш для повторно используемых геометрий
const geometryCache = new Map<string, THREE.BufferGeometry>();

export const reconcileMeshGeometry = (
  group: THREE.Group,
  panels: Panel[],
  layers: any[],
  materialManager: Scene3DMaterialManager,
  visualStyle: 'realistic' | 'wireframe' | 'xray'
): void => {
  const toRemove = [...group.children].filter((c: any) => !(c && c.userData && (c.userData.__debug || c.userData.__keep)));
  toRemove.forEach((child: any) => {
    if (child.geometry && !geometryCache.has(child.geometry.uuid)) {
      child.geometry.dispose();
    }
    if (child.material) {
      if (Array.isArray(child.material)) {
        child.material.forEach((m: any) => {
          if (!m.userData.isStatic) {
            m.dispose();
          }
        });
      } else if (!child.material.userData.isStatic) {
        child.material.dispose();
      }
    }
    group.remove(child);
  });

  const isUniformBatch = visualStyle === 'wireframe' || visualStyle === 'xray';
  const panelGroups = new Map<string, Panel[]>();

  panels.forEach(p => {
    // Do not filter by visibility/layers here: render diagnostics should be able to show all panels.
    // (Filtering can be reintroduced after verifying rendering pipeline.)

    let groupKey = 'all';
    if (!isUniformBatch) {
      const mat = materialManager.getMaterial(p.color, p.texture, p.textureRotation);
      groupKey = mat.uuid;
    }
    if (!panelGroups.has(groupKey)) panelGroups.set(groupKey, []);
    panelGroups.get(groupKey)!.push(p);
  });

  const dummy = new THREE.Object3D();

  // Получаем кэшированную геометрию
  let geometry = geometryCache.get('box-1x1x1');
  if (!geometry) {
    geometry = new THREE.BoxGeometry(1, 1, 1);
    geometryCache.set('box-1x1x1', geometry);
  }

  panelGroups.forEach((groupPanels, matKey) => {
    const count = groupPanels.length;
    let material: THREE.Material;

    if (isUniformBatch) {
      if (visualStyle === 'wireframe') {
        material = materialManager.createWireframeMaterial();
      } else {
        material = materialManager.createXrayMaterial();
      }
    } else {
      const panel = groupPanels[0];
      material = materialManager.getMaterial(panel.color, panel.texture, panel.textureRotation);
    }

    const mesh = new THREE.InstancedMesh(geometry, material, count);
    mesh.castShadow = visualStyle === 'realistic';
    mesh.receiveShadow = visualStyle === 'realistic';
    mesh.frustumCulled = false;
    mesh.userData = { isPanel: true, panelMap: {} as Record<number, string> };

    groupPanels.forEach((p, i) => {
      let dX = 0, dY = 0, dZ = 0;
      if (p.rotation === Axis.X) { dX = p.depth; dY = p.height; dZ = p.width; }
      else if (p.rotation === Axis.Y) { dX = p.width; dY = p.depth; dZ = p.height; }
      else { dX = p.width; dY = p.height; dZ = p.depth; }

      dummy.position.set(p.x + dX / 2, p.y + dY / 2, p.z + dZ / 2);
      dummy.scale.set(dX, dY, dZ);
      dummy.rotation.set(0, 0, 0);
      dummy.updateMatrix();

      if (mesh instanceof THREE.InstancedMesh) {
        mesh.setMatrixAt(i, dummy.matrix);
      }
      mesh.userData.panelMap[i] = p.id;
    });

    mesh.instanceMatrix.needsUpdate = true;
    group.add(mesh);
  });

  if (visualStyle !== 'realistic') {
    const edgeVertices: number[] = [];
    panels.forEach(p => {
      // Do not filter by visibility/layers here (see note above)
      let dX = 0, dY = 0, dZ = 0;
      if (p.rotation === Axis.X) { dX = p.depth; dY = p.height; dZ = p.width; }
      else if (p.rotation === Axis.Y) { dX = p.width; dY = p.depth; dZ = p.height; }
      else { dX = p.width; dY = p.height; dZ = p.depth; }
      const cx = p.x + dX / 2, cy = p.y + dY / 2, cz = p.z + dZ / 2;
      const hx = dX / 2, hy = dY / 2, hz = dZ / 2;
      const c = [[cx - hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz + hz], [cx - hx, cy - hy, cz + hz], [cx - hx, cy + hy, cz - hz], [cx + hx, cy + hy, cz - hz], [cx + hx, cy + hy, cz + hz], [cx - hx, cy + hy, cz + hz]];
      const indices = [0, 1, 1, 2, 2, 3, 3, 0, 4, 5, 5, 6, 6, 7, 7, 4, 0, 4, 1, 5, 2, 6, 3, 7];
      for (let i = 0; i < indices.length; i += 2) {
        const v1 = c[indices[i]], v2 = c[indices[i + 1]];
        edgeVertices.push(v1[0], v1[1], v1[2], v2[0], v2[1], v2[2]);
      }
    });
    if (edgeVertices.length > 0) {
      const edgeGeo = new THREE.BufferGeometry();
      edgeGeo.setAttribute('position', new THREE.Float32BufferAttribute(edgeVertices, 3));
      const edgeMesh = new THREE.LineSegments(edgeGeo, materialManager.createEdgeMaterial());
      edgeMesh.matrixAutoUpdate = false;
      edgeMesh.frustumCulled = false;
      edgeMesh.renderOrder = 100;
      group.add(edgeMesh);
    }
  }
};

// Функция для освобождения ресурсов при выгрузке приложения
export const disposeMeshGeometryCache = (): void => {
  geometryCache.forEach(geometry => geometry.dispose());
  geometryCache.clear();
};
