import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

export interface Scene3DRendererSetup {
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  renderer: THREE.WebGLRenderer;
  orbitControls: OrbitControls;
  trackballControls: TrackballControls;
  transformControls: TransformControls;
  gridHelper: THREE.GridHelper;
  axesHelper: THREE.AxesHelper;
  panelsGroup: THREE.Group;
  selectionGroup: THREE.Group;
}

export const createScene3DRenderer = (container: HTMLDivElement): Scene3DRendererSetup => {
  const isMobile = /Android|iPhone|iPad/i.test(navigator.userAgent) || window.innerWidth < 768;
  const width = container.clientWidth;
  const height = container.clientHeight;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#1a1a1a');
  scene.fog = new THREE.FogExp2(0x1a1a1a, 0.00002);

  const camera = new THREE.PerspectiveCamera(45, width / height, 10, 200000);
  camera.position.set(2000, 1500, 2500);

  const renderer = new THREE.WebGLRenderer({ 
    antialias: !isMobile, 
    logarithmicDepthBuffer: !isMobile,
    powerPreference: 'high-performance',
    alpha: false
  });
  renderer.setSize(width, height);
  renderer.shadowMap.enabled = !isMobile;
  renderer.shadowMap.type = isMobile ? THREE.PCFShadowMap : THREE.PCFSoftShadowMap;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, isMobile ? 1 : 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  container.appendChild(renderer.domElement);

  const controlsDomElement = renderer.domElement as unknown as HTMLElement;

  const orbitControls = new OrbitControls(camera, controlsDomElement);
  orbitControls.enableZoom = true;
  orbitControls.enableDamping = true;
  orbitControls.dampingFactor = 0.08;
  orbitControls.enablePan = true;
  orbitControls.maxPolarAngle = Math.PI / 2 - 0.05;
  orbitControls.minDistance = 100;
  orbitControls.maxDistance = 50000;

  const trackballControls = new TrackballControls(camera, controlsDomElement);
  trackballControls.noRotate = true;
  trackballControls.noPan = true;
  trackballControls.noZoom = false;
  trackballControls.zoomSpeed = 1.2;
  trackballControls.staticMoving = true;
  trackballControls.dynamicDampingFactor = 0.3;

  const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, isMobile ? 0.5 : 0.7);
  scene.add(hemiLight);

  const dirLight = new THREE.DirectionalLight(0xffffff, isMobile ? 0.6 : 0.8);
  dirLight.position.set(1500, 3000, 1500);
  dirLight.castShadow = !isMobile;
  dirLight.shadow.mapSize.width = isMobile ? 512 : 1024;
  dirLight.shadow.mapSize.height = isMobile ? 512 : 1024;
  dirLight.shadow.camera.near = 100;
  dirLight.shadow.camera.far = 10000;
  dirLight.shadow.camera.left = -2000;
  dirLight.shadow.camera.right = 2000;
  dirLight.shadow.camera.top = 2000;
  dirLight.shadow.camera.bottom = -2000;
  scene.add(dirLight);

  const panelsGroup = new THREE.Group();
  panelsGroup.name = 'panels-container';
  scene.add(panelsGroup);

  const selectionGroup = new THREE.Group();
  selectionGroup.name = 'selection-highlight';
  scene.add(selectionGroup);

  const gridHelper = new THREE.GridHelper(isMobile ? 5000 : 10000, isMobile ? 50 : 100, 0x444444, 0x222222);
  gridHelper.position.y = -1;
  scene.add(gridHelper);

  const axesHelper = new THREE.AxesHelper(isMobile ? 250 : 500);
  scene.add(axesHelper);

  const transformControls = new TransformControls(camera, controlsDomElement);
  transformControls.size = isMobile ? 1.5 : 1.0;
  
  if (transformControls instanceof THREE.Object3D) {
    scene.add(transformControls);
  }

  return {
    scene,
    camera,
    renderer,
    orbitControls,
    trackballControls,
    transformControls,
    gridHelper,
    axesHelper,
    panelsGroup,
    selectionGroup,
  };
};

export const disposeScene3DRenderer = (setup: Scene3DRendererSetup, container: HTMLDivElement): void => {
  setup.renderer.dispose();
  setup.orbitControls.dispose();
  setup.trackballControls.dispose();
  setup.transformControls.dispose();
  
  // Clear all scene objects
  while (setup.scene.children.length > 0) {
    const child = setup.scene.children[0];
    setup.scene.remove(child);
    
    if (child instanceof THREE.Mesh) {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach(mat => mat.dispose());
        } else {
          child.material.dispose();
        }
      }
    }
  }
  
  if (container) {
    container.innerHTML = '';
  }
};
