import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

let scene, camera, renderer, controls, currentMesh;
let wireframeMode = false, autoRotate = false;
const materials = { solid: null, wireframe: null };

function initThree() {
  const container = document.getElementById('canvas-container');
  const width = container.clientWidth;
  const height = container.clientHeight;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x10141d);

  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 5000);
  camera.position.set(120, 120, 150);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.shadowMap.enabled = true;
  container.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambientLight);

  const dirLight1 = new THREE.DirectionalLight(0x00d2ff, 1.0);
  dirLight1.position.set(100, 200, 100);
  scene.add(dirLight1);

  const dirLight2 = new THREE.DirectionalLight(0x7000ff, 0.6);
  dirLight2.position.set(-100, -100, -100);
  scene.add(dirLight2);

  const hemiLight = new THREE.HemisphereLight(0x00d2ff, 0x0a0c10, 0.3);
  scene.add(hemiLight);

  const gridHelper = new THREE.GridHelper(400, 40, 0x00d2ff, 0x1a2030);
  gridHelper.position.y = -20;
  scene.add(gridHelper);

  materials.solid = new THREE.MeshStandardMaterial({
    color: 0x00d2ff,
    roughness: 0.3,
    metalness: 0.4,
  });
  materials.wireframe = new THREE.MeshStandardMaterial({
    color: 0x00d2ff,
    wireframe: true,
    transparent: true,
    opacity: 0.6,
  });

  window.addEventListener('resize', onWindowResize);
  animate();
}

function onWindowResize() {
  const container = document.getElementById('canvas-container');
  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
}

function animate() {
  requestAnimationFrame(animate);
  if (autoRotate && currentMesh) {
    currentMesh.rotation.y += 0.005;
  }
  controls.update();
  renderer.render(scene, camera);
}

window.resetCamera = function () {
  if (!currentMesh) return;
  const r = currentMesh.geometry.boundingSphere?.radius || 100;
  camera.position.set(r * 2, r * 2, r * 2.5);
  controls.target.set(0, 0, 0);
};

window.toggleWireframe = function () {
  wireframeMode = !wireframeMode;
  document.querySelector('.vp-btn[title="Каркас"]')?.classList.toggle('active', wireframeMode);
  if (currentMesh) {
    currentMesh.material = wireframeMode ? materials.wireframe : materials.solid;
  }
};

window.toggleAutoRotate = function () {
  autoRotate = !autoRotate;
  document.querySelector('.vp-btn[title="Авто-вращение"]')?.classList.toggle('active', autoRotate);
};

// Tab switching
window.showTab = function (tab) {
  document.querySelectorAll('.template-chip').forEach((c, i) => {
    c.classList.toggle('active', ['nl', 'editor', 'templates', 'help'][i] === tab);
  });
  document.querySelectorAll('.tab-body').forEach((b) => b.classList.remove('active'));
  document.getElementById(`tab-${tab}`)?.classList.add('active');
  if (tab === 'templates') loadTemplates();
};

// Line numbers
function updateLineNumbers() {
  const editor = document.getElementById('code-editor');
  const lines = editor.value.split('\n').length;
  const nums = document.getElementById('line-numbers');
  nums.innerHTML = Array.from({ length: lines }, (_, i) => `<div>${i + 1}</div>`).join('');
}

document.addEventListener('DOMContentLoaded', () => {
  const editor = document.getElementById('code-editor');
  editor.addEventListener('input', updateLineNumbers);
  editor.addEventListener('scroll', () => {
    document.getElementById('line-numbers').scrollTop = editor.scrollTop;
  });
  updateLineNumbers();
  initThree();
  autoLoadDefault();
});

async function autoLoadDefault() {
  try {
    const res = await fetch('/api/default-model');
    const data = await res.json();
    if (data.status === 'success' && data.stl) {
      setStatus('Загрузка модели...', 'var(--accent-orange)');
      loadSTL(data.stl);
      document.getElementById('viewport-controls').style.display = 'flex';
      document.getElementById('download-bar').style.display = 'flex';
      if (data.stl) document.getElementById('dl-stl').href = data.stl;
      if (data.step) document.getElementById('dl-step').href = data.step;
      setStatus(data.name || 'Готов', 'var(--accent-green)');
    }
  } catch (e) {
    // No default model, that's fine
  }
}

// Templates
async function loadTemplates() {
  const list = document.getElementById('templates-list');
  if (list.children.length > 0) return;
  try {
    const res = await fetch('/api/templates');
    const data = await res.json();
    for (const [id, info] of Object.entries(data)) {
      const card = document.createElement('div');
      card.className = 'template-card';
      card.innerHTML = `<div class="template-name">${info.name}</div><div class="template-desc">${info.description}</div>`;
      card.onclick = () => loadTemplate(id);
      list.appendChild(card);
    }
  } catch (e) {
    list.innerHTML = '<div style="color:var(--accent-red);padding:12px;">Ошибка загрузки шаблонов</div>';
  }
}

async function loadTemplate(id) {
  setStatus('Загрузка шаблона...', 'var(--accent-orange)');
  try {
    const res = await fetch(`/api/templates/${id}/code`);
    const data = await res.json();
    document.getElementById('code-editor').value = data.code;
    updateLineNumbers();
    showTab('editor');
    setStatus('Шаблон загружен', 'var(--accent-green)');
  } catch (e) {
    setStatus('Ошибка загрузки', 'var(--accent-red)');
  }
}

// Generate
window.generateFromCode = async function () {
  const code = document.getElementById('code-editor').value.trim();
  if (!code) {
    setStatus('Нет кода', 'var(--accent-red)');
    return;
  }

  const btn = document.getElementById('btn-generate');
  const btnText = document.getElementById('btn-text');
  btn.disabled = true;
  btn.classList.add('loading');
  btnText.textContent = 'Генерация...';
  setStatus('Выполнение build123d...', 'var(--accent-orange)');

  try {
    const fmt = document.getElementById('export-format').value;
    const res = await fetch('/api/generate/code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, export_fmt: fmt }),
    });

    const data = await res.json();

    if (data.status === 'success') {
      setStatus('Модель сгенерирована!', 'var(--accent-green)');
      document.getElementById('viewport-controls').style.display = 'flex';
      document.getElementById('download-bar').style.display = 'flex';

      if (data.files.stl) {
        document.getElementById('dl-stl').href = data.files.stl;
        document.getElementById('dl-stl').style.display = 'flex';
        loadSTL(data.files.stl);
      }
      if (data.files.step) {
        document.getElementById('dl-step').href = data.files.step;
        document.getElementById('dl-step').style.display = 'flex';
      }
    } else {
      setStatus('Ошибка', 'var(--accent-red)');
      showError(data.detail || data.error || 'Неизвестная ошибка');
    }
  } catch (e) {
    setStatus('Ошибка соединения', 'var(--accent-red)');
    showError(e.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
    btnText.textContent = 'Сгенерировать';
  }
};

// NL Generation
window.generateFromNL = async function () {
  const desc = document.getElementById('nl-input').value.trim();
  if (!desc) {
    setNLStatus('Опиши модель', 'error');
    return;
  }

  const btn = document.getElementById('btn-nl');
  const btnText = document.getElementById('nl-btn-text');
  btn.disabled = true;
  btn.classList.add('loading');
  btnText.textContent = 'AI генерирует код...';
  setNLStatus('Генерация build123d кода через AI...', 'loading');
  setStatus('AI генерация...', 'var(--accent-orange)');

  try {
    const res = await fetch('/api/generate/nl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: desc }),
    });

    const data = await res.json();

    if (data.status === 'success') {
      setNLStatus('Модель сгенерирована из описания!', 'success');
      setStatus('Модель готова!', 'var(--accent-green)');
      document.getElementById('viewport-controls').style.display = 'flex';
      document.getElementById('download-bar').style.display = 'flex';

      // Show generated code in editor
      if (data.code) {
        document.getElementById('code-editor').value = data.code;
        updateLineNumbers();
      }

      if (data.files.stl) {
        document.getElementById('dl-stl').href = data.files.stl;
        loadSTL(data.files.stl);
      }
      if (data.files.step) {
        document.getElementById('dl-step').href = data.files.step;
      }
    } else if (data.status === 'partial') {
      setNLStatus('AI сгенерировал код, но выполнение не удалось. Код вставлен в редактор.', 'error');
      if (data.code) {
        document.getElementById('code-editor').value = data.code;
        updateLineNumbers();
        showTab('editor');
      }
      showError(data.error || 'Ошибка выполнения');
    } else {
      setNLStatus(data.detail || data.error || 'Ошибка', 'error');
      setStatus('Ошибка', 'var(--accent-red)');
    }
  } catch (e) {
    setNLStatus('Ошибка соединения: ' + e.message, 'error');
    setStatus('Ошибка', 'var(--accent-red)');
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
    btnText.textContent = 'Сгенерировать из описания';
  }
};

function setNLStatus(text, type) {
  const el = document.getElementById('nl-status');
  el.textContent = text;
  el.className = 'nl-status ' + type;
}

function loadSTL(url) {
  const loader = new STLLoader();
  loader.load(url, (geometry) => {
    if (currentMesh) {
      scene.remove(currentMesh);
      currentMesh.geometry.dispose();
    }
    geometry.center();
    geometry.computeVertexNormals();
    currentMesh = new THREE.Mesh(geometry, wireframeMode ? materials.wireframe : materials.solid);
    scene.add(currentMesh);
    geometry.computeBoundingSphere();
    const radius = geometry.boundingSphere.radius;
    camera.position.set(radius * 1.8, radius * 1.8, radius * 2.2);
    controls.target.set(0, 0, 0);
  });
}

function setStatus(text, color) {
  const el = document.getElementById('status-text');
  el.textContent = text;
  el.style.color = color;
}

function showError(msg) {
  let box = document.querySelector('.error-display');
  if (!box) {
    box = document.createElement('div');
    box.className = 'error-display';
    document.getElementById('tab-editor').appendChild(box);
  }
  box.textContent = msg;
  box.style.display = 'block';
  setTimeout(() => { box.style.display = 'none'; }, 15000);
}

// Helper functions
window.formatCode = function () {
  const editor = document.getElementById('code-editor');
  editor.value = editor.value
    .split('\n')
    .map((l) => l.trimEnd())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n');
  updateLineNumbers();
};

window.clearCode = function () {
  document.getElementById('code-editor').value = '';
  updateLineNumbers();
  document.querySelector('.error-display')?.remove();
};

window.loadTemplateHelp = function () {
  showTab('help');
};
