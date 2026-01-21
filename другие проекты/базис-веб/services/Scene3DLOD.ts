import * as THREE from 'three';
import { Panel, Axis, TextureType } from '../types';
import { Scene3DMaterialManager } from './Scene3DMaterial';

export interface LODLevel {
  distance: number;
  geometry: THREE.BufferGeometry;
  material: THREE.Material;
  instanceCount?: number;
}

export class Scene3DLODManager {
  private lodObjects = new Map<string, THREE.LOD>();
  private camera: THREE.Camera;
  private materialManager: Scene3DMaterialManager;
  private staticGeometryCache = new Map<string, THREE.BufferGeometry>();

  constructor(camera: THREE.Camera, materialManager: Scene3DMaterialManager) {
    this.camera = camera;
    this.materialManager = materialManager;
  }

  /**
   * Создает LOD объект для группы панелей
   */
  createLODForPanels(panels: Panel[], groupKey: string): THREE.LOD {
    const lod = new THREE.LOD();

    // Уровень 0: Полная детализация (близко)
    const highDetail = this.createHighDetailLevel(panels);
    lod.addLevel(highDetail, 0);

    // Уровень 1: Средняя детализация (среднее расстояние)
    const mediumDetail = this.createMediumDetailLevel(panels);
    lod.addLevel(mediumDetail, 800);

    // Уровень 2: Низкая детализация (далеко)
    const lowDetail = this.createLowDetailLevel(panels);
    lod.addLevel(lowDetail, 2000);

    // Уровень 3: Очень низкая детализация (очень далеко)
    const veryLowDetail = this.createVeryLowDetailLevel(panels);
    lod.addLevel(veryLowDetail, 4000);

    this.lodObjects.set(groupKey, lod);
    return lod;
  }

  /**
   * Создает высокодетализированный уровень (полные панели)
   */
  private createHighDetailLevel(panels: Panel[]): THREE.InstancedMesh {
    const cacheKey = 'box-1x1x1';
    let geometry = this.staticGeometryCache.get(cacheKey);
    if (!geometry) {
      geometry = new THREE.BoxGeometry(1, 1, 1);
      this.staticGeometryCache.set(cacheKey, geometry);
    }

    const panel = panels[0];
    const material = this.materialManager.getMaterial(
      panel?.color || '#ffffff',
      panel?.texture || TextureType.NONE,
      panel?.textureRotation || 0
    );

    const mesh = new THREE.InstancedMesh(geometry, material, panels.length);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.frustumCulled = false;

    const dummy = new THREE.Object3D();
    panels.forEach((panel, i) => {
      let dX = 0, dY = 0, dZ = 0;
      if (panel.rotation === Axis.X) { dX = panel.depth; dY = panel.height; dZ = panel.width; }
      else if (panel.rotation === Axis.Y) { dX = panel.width; dY = panel.depth; dZ = panel.height; }
      else { dX = panel.width; dY = panel.height; dZ = panel.depth; }

      dummy.position.set(panel.x + dX / 2, panel.y + dY / 2, panel.z + dZ / 2);
      dummy.scale.set(dX, dY, dZ);
      dummy.updateMatrix();

      mesh.setMatrixAt(i, dummy.matrix);
    });

    mesh.instanceMatrix.needsUpdate = true;
    return mesh;
  }

  /**
   * Создает среднедетализированный уровень (упрощенные панели)
   */
  private createMediumDetailLevel(panels: Panel[]): THREE.InstancedMesh {
    const cacheKey = 'plane-1x1';
    let geometry = this.staticGeometryCache.get(cacheKey);
    if (!geometry) {
      geometry = new THREE.PlaneGeometry(1, 1);
      this.staticGeometryCache.set(cacheKey, geometry);
    }

    const panel = panels[0];
    const material = this.materialManager.getMaterial(
      panel?.color || '#ffffff',
      panel?.texture || TextureType.NONE,
      panel?.textureRotation || 0
    );

    const mesh = new THREE.InstancedMesh(geometry, material, panels.length);
    mesh.castShadow = false;
    mesh.receiveShadow = false;
    mesh.frustumCulled = false;

    const dummy = new THREE.Object3D();
    panels.forEach((panel, i) => {
      let dX = 0, dY = 0, dZ = 0;
      if (panel.rotation === Axis.X) { dX = panel.depth; dY = panel.height; dZ = panel.width; }
      else if (panel.rotation === Axis.Y) { dX = panel.width; dY = panel.depth; dZ = panel.height; }
      else { dX = panel.width; dY = panel.height; dZ = panel.depth; }

      // Для плоскости выбираем самую большую грань
      const maxDim = Math.max(dX, dY, dZ);
      if (maxDim === dX) {
        dummy.position.set(panel.x + dX / 2, panel.y + dY / 2, panel.z + dZ / 2);
        dummy.scale.set(dY, dZ, 1);
        dummy.rotation.set(0, Math.PI / 2, 0);
      } else if (maxDim === dY) {
        dummy.position.set(panel.x + dX / 2, panel.y + dY / 2, panel.z + dZ / 2);
        dummy.scale.set(dX, dZ, 1);
        dummy.rotation.set(Math.PI / 2, 0, 0);
      } else {
        dummy.position.set(panel.x + dX / 2, panel.y + dY / 2, panel.z + dZ / 2);
        dummy.scale.set(dX, dY, 1);
      }

      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    });

    mesh.instanceMatrix.needsUpdate = true;
    return mesh;
  }

  /**
   * Создает низкодетализированный уровень (точки)
   */
  private createLowDetailLevel(panels: Panel[]): THREE.Points {
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(panels.length * 3);
    const colors = new Float32Array(panels.length * 3);

    panels.forEach((panel, i) => {
      let dX = 0, dY = 0, dZ = 0;
      if (panel.rotation === Axis.X) { dX = panel.depth; dY = panel.height; dZ = panel.width; }
      else if (panel.rotation === Axis.Y) { dX = panel.width; dY = panel.depth; dZ = panel.height; }
      else { dX = panel.width; dY = panel.height; dZ = panel.depth; }

      const centerX = panel.x + dX / 2;
      const centerY = panel.y + dY / 2;
      const centerZ = panel.z + dZ / 2;

      positions[i * 3] = centerX;
      positions[i * 3 + 1] = centerY;
      positions[i * 3 + 2] = centerZ;

      // Простой цвет на основе размера
      const intensity = Math.min(1, Math.max(dX, dY, dZ) / 1000);
      colors[i * 3] = intensity;
      colors[i * 3 + 1] = intensity;
      colors[i * 3 + 2] = intensity;
    });

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: 8,
      vertexColors: true,
      transparent: true,
      opacity: 0.7,
      depthWrite: false
    });

    const points = new THREE.Points(geometry, material);
    points.frustumCulled = false;
    return points;
  }

  /**
   * Создает очень низкодетализированный уровень (bounding box)
   */
  private createVeryLowDetailLevel(panels: Panel[]): THREE.LineSegments {
    // Создаем bounding box для всей группы панелей
    const box = new THREE.Box3();
    panels.forEach(panel => {
      let dX = 0, dY = 0, dZ = 0;
      if (panel.rotation === Axis.X) { dX = panel.depth; dY = panel.height; dZ = panel.width; }
      else if (panel.rotation === Axis.Y) { dX = panel.width; dY = panel.depth; dZ = panel.height; }
      else { dX = panel.width; dY = panel.height; dZ = panel.depth; }

      const min = new THREE.Vector3(panel.x, panel.y, panel.z);
      const max = new THREE.Vector3(panel.x + dX, panel.y + dY, panel.z + dZ);
      box.expandByPoint(min);
      box.expandByPoint(max);
    });

    const boxGeometry = new THREE.BoxGeometry(
      box.max.x - box.min.x,
      box.max.y - box.min.y,
      box.max.z - box.min.z
    );

    const edges = new THREE.EdgesGeometry(boxGeometry);
    const material = new THREE.LineBasicMaterial({
      color: 0x888888,
      transparent: true,
      opacity: 0.5,
      depthWrite: false
    });

    const lineSegments = new THREE.LineSegments(edges, material);
    lineSegments.position.copy(box.getCenter(new THREE.Vector3()));
    lineSegments.frustumCulled = false;

    return lineSegments;
  }

  /**
   * Обновляет LOD объекты (вызывается в animation loop)
   */
  update(): void {
    this.lodObjects.forEach(lod => {
      lod.update(this.camera);
    });
  }

  /**
   * Очищает все LOD объекты
   */
  dispose(): void {
    this.lodObjects.forEach(lod => {
      // Dispose всех уровней LOD
      for (let i = lod.levels.length - 1; i >= 0; i--) {
        const level = lod.levels[i];
        if (level.object) {
          if (level.object instanceof THREE.InstancedMesh) {
            // Не диспоузим геометрию из кеша
            if (Array.isArray(level.object.material)) {
              level.object.material.forEach(mat => mat.dispose());
            } else {
              level.object.material.dispose();
            }
          } else if (level.object instanceof THREE.Points || level.object instanceof THREE.LineSegments) {
            level.object.geometry.dispose();
            level.object.material.dispose();
          }
        }
      }
    });
    
    // Диспоузим только кешированную геометрию при полном удалении менеджера
    this.staticGeometryCache.forEach(geometry => geometry.dispose());
    this.staticGeometryCache.clear();
    this.lodObjects.clear();
  }
}