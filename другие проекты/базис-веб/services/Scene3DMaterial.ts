import * as THREE from 'three';
import { TextureType } from '../types';

export const isDirectionalTexture = (t: TextureType): boolean => {
  return t === TextureType.WOOD_OAK || t === TextureType.WOOD_WALNUT || t === TextureType.WOOD_ASH;
};

export class Scene3DMaterialManager {
  private materialCache: Map<string, THREE.Material> = new Map();
  private textureCache: Map<string, THREE.Texture> = new Map();
  private renderer: THREE.WebGLRenderer | null = null;
  private staticMaterials = new Map<string, THREE.Material>();

  constructor(renderer?: THREE.WebGLRenderer) {
    this.renderer = renderer || null;
    this.initializeStaticMaterials();
  }

  private initializeStaticMaterials(): void {
    // Wireframe material (cached)
    const wireframeMat = new THREE.MeshBasicMaterial({
      color: 0x1a1a1a,
      transparent: true,
      opacity: 0.1,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    this.staticMaterials.set('wireframe', wireframeMat);

    // X-ray material (cached)
    const xrayMat = new THREE.MeshBasicMaterial({
      color: 0x60a5fa,
      transparent: true,
      opacity: 0.15,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    });
    this.staticMaterials.set('xray', xrayMat);

    // Edge material (cached)
    const edgeMat = new THREE.LineBasicMaterial({
      color: 0x000000,
      transparent: true,
      opacity: 0.4,
      depthTest: true,
      depthWrite: false,
    });
    this.staticMaterials.set('edge', edgeMat);
  }

  setRenderer(renderer: THREE.WebGLRenderer): void {
    this.renderer = renderer;
  }

  getMaterial(color: string, textureType: TextureType, rotation: number): THREE.Material {
    const effectiveRotation = isDirectionalTexture(textureType) ? rotation : 0;
    const key = `${color}:${textureType}:${effectiveRotation}`;

    if (!this.materialCache.has(key)) {
      let map: THREE.Texture | null = null;

      if (textureType !== TextureType.NONE) {
        const texKey = `${textureType}:${effectiveRotation}`;
        if (!this.textureCache.has(texKey)) {
          const canvas = document.createElement('canvas');
          canvas.width = 256; // Уменьшили разрешение для лучшей производительности
          canvas.height = 256;
          const ctx = canvas.getContext('2d');
          if (ctx) {
            ctx.fillStyle = textureType === TextureType.CONCRETE ? '#e0e0e0' : '#f5f5f5';
            ctx.fillRect(0, 0, 256, 256);

            if (isDirectionalTexture(textureType)) {
              ctx.fillStyle = 'rgba(100, 70, 40, 0.08)';
              const angle = effectiveRotation === 90 ? 0 : Math.PI / 2;
              ctx.save();
              ctx.translate(128, 128);
              ctx.rotate(angle);
              ctx.translate(-128, -128);
              for (let i = 0; i < 400; i++) { // Уменьшили количество линий для скорости
                const x = Math.random() * 256;
                const w = 1 + Math.random() * 2;
                const h = 20 + Math.random() * 100;
                ctx.globalAlpha = 0.05 + Math.random() * 0.05;
                ctx.fillRect(x, Math.random() * 256, w, h);
              }
              ctx.restore();
            } else if (textureType === TextureType.CONCRETE) {
              for (let i = 0; i < 5000; i++) { // Уменьшили количество точек
                ctx.fillStyle = Math.random() > 0.5 ? '#cccccc' : '#bbbbbb';
                ctx.fillRect(Math.random() * 256, Math.random() * 256, 2, 2);
              }
            }

            const tex = new THREE.CanvasTexture(canvas);
            tex.anisotropy = this.renderer?.capabilities.getMaxAnisotropy() || 2;
            tex.colorSpace = THREE.SRGBColorSpace;
            tex.minFilter = THREE.LinearFilter;
            tex.magFilter = THREE.LinearFilter;
            tex.wrapS = THREE.RepeatWrapping;
            tex.wrapT = THREE.RepeatWrapping;
            this.textureCache.set(texKey, tex);
          }
        }
        map = this.textureCache.get(texKey) || null;
      }

      const mat = new THREE.MeshStandardMaterial({ // Используем более простой материал
        color: new THREE.Color(color),
        map: map,
        roughness: 0.7,
        metalness: 0.1,
        transparent: false,
        opacity: 1.0,
        side: THREE.FrontSide,
        flatShading: false,
        envMapIntensity: 0.0
      });
      this.materialCache.set(key, mat);
    }
    return this.materialCache.get(key)!;
  }

  createWireframeMaterial(): THREE.MeshBasicMaterial {
    return this.staticMaterials.get('wireframe') as unknown as THREE.MeshBasicMaterial;
  }

  createXrayMaterial(): THREE.MeshBasicMaterial {
    return this.staticMaterials.get('xray') as unknown as THREE.MeshBasicMaterial;
  }

  createEdgeMaterial(): THREE.LineBasicMaterial {
    return this.staticMaterials.get('edge') as unknown as THREE.LineBasicMaterial;
  }

  dispose(): void {
    this.materialCache.forEach(m => m.dispose());
    this.textureCache.forEach(t => t.dispose());
    this.staticMaterials.forEach(m => m.dispose());
    this.materialCache.clear();
    this.textureCache.clear();
    this.staticMaterials.clear();
  }
}
