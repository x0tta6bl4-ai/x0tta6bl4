# 🔌 Интеграция Neural CAD Generator

## 1️⃣ Копировать обученные модели

После запуска `python scripts/train_neural_cad.py`, скопировать файлы:

```bash
# Скопировать модели в браузер
mkdir -p public/models
cp models/furniture-encoder-v1.onnx public/models/
cp models/furniture-decoder-v1.onnx public/models/
cp models/metadata.json public/models/

# Проверить
ls -lah public/models/
```

## 2️⃣ Выбрать один из способов интеграции

### Способ A: Использовать обновлённый App.tsx (РЕКОМЕНДУЕТСЯ)

```bash
# Заменить App.tsx на версию с Neural интеграцией
mv App.tsx App.original.tsx
cp AppWithNeural.tsx App.tsx

# Или вручную скопировать необходимые части
```

**Что добавлено:**
- VIEW MODE SWITCHER слева (Wizard / Design / Neural Gen)
- Клавиша `Ctrl+N` для быстрого входа в Neural view
- Обработчик события `neural-cabinet-generated`
- Обновлённая правая панель для Neural режима

### Способ B: Ручная интеграция (Для уже модифицированного App.tsx)

#### Шаг 1: Добавить импорт

```typescript
// App.tsx (добавить в начало)

// Lazy load компонент
const NeuralGenerationPanel = React.lazy(() => 
  import('./components/NeuralGenerationPanel')
);
```

#### Шаг 2: Добавить новый режим в ViewMode enum

```typescript
enum ViewMode {
  DESIGN = 'design',
  WIZARD = 'wizard',
  CUT_LIST = 'cut_list',
  DRAWING = 'drawing',
  NESTING = 'nesting',
  PRODUCTION = 'production',
  NEURAL = 'neural',  // ← Добавить эту строку
}
```

#### Шаг 3: Добавить обработчик события при инициализации

```typescript
useEffect(() => {
  // ... остальной код инициализации ...

  // ДОБАВИТЬ: Слушать события от neural generator
  const handleNeuralGeneration = (event: CustomEvent) => {
    const { geometry, parameters } = event.detail;
    console.log(`✨ Generated ${geometry.metrics.vertexCount} vertices`);
    // Можно обновить state или dispatch event дальше
  };

  window.addEventListener('neural-cabinet-generated', handleNeuralGeneration as EventListener);
  
  return () => {
    window.removeEventListener('neural-cabinet-generated', handleNeuralGeneration as EventListener);
  };
}, []);
```

#### Шаг 4: Добавить кнопку в левую панель (SidePanel)

```typescript
// Добавить в sidePanel после существующего SidePanel компонента:

{viewMode === ViewMode.NEURAL ? null : (
  <div className="px-4 py-2 border-b border-slate-700">
    <button
      onClick={() => setViewMode(ViewMode.NEURAL)}
      className="w-full px-3 py-2 rounded text-xs font-medium bg-cyan-600 text-white hover:bg-cyan-700 transition"
    >
      ✨ Neural Generator
    </button>
  </div>
)}
```

#### Шаг 5: Добавить NEURAL режим в mainContent

```typescript
// mainContent в MainLayout - добавить новый блок

{viewMode === ViewMode.NEURAL && (
  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-950 to-slate-900 p-8">
    <Suspense
      fallback={
        <div className="text-center text-slate-400">
          <div className="w-12 h-12 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-sm">Loading Neural Generator...</p>
        </div>
      }
    >
      <NeuralGenerationPanel />
    </Suspense>
  </div>
)}
```

#### Шаг 6: Обновить rightPanel для Neural режима

```typescript
rightPanel={
  viewMode === ViewMode.NEURAL ? (
    // В NEURAL режиме показать статистику Neural Gen, если нужна
    <div className="p-4 text-slate-400 text-sm">
      <p>📊 Статистика генерации...</p>
    </div>
  ) : (
    // В других режимах показать Properties Panel
    <PropertiesPanel
      selectedPanel={selectedPanel}
      onPanelUpdate={(id, changes) => updatePanel(id, changes)}
      materials={MATERIAL_LIBRARY}
    />
  )
}
```

## 3️⃣ Проверить работу

```bash
# 1. Запустить dev сервер
npm run dev

# 2. Открыть браузер
# http://localhost:3000

# 3. Найти кнопку "✨ Neural Gen" или нажать Ctrl+N

# 4. Видеть:
# - Параметры слайдеры (ширина, высота, глубина и т.д.)
# - Кнопка "✨ Сгенерировать 3D"
# - Прогресс бар во время генерации
# - Статистика (вершины, грани, время, уверенность)
```

## 4️⃣ Интеграция с 3D viewport (опционально)

Если хотите видеть 3D результат в Scene3DSimple:

```typescript
// components/Scene3DSimple.tsx - добавить

useEffect(() => {
  const handleNeuralGeneration = (event: CustomEvent) => {
    const { geometry, parameters } = event.detail;
    
    // Создать Three.js BufferGeometry из neural результата
    const bufferGeometry = new THREE.BufferGeometry();
    
    // Vertices
    const positions = new Float32Array(geometry.vertices.length * 3);
    geometry.vertices.forEach((v, i) => {
      positions[i * 3] = v.x;
      positions[i * 3 + 1] = v.y;
      positions[i * 3 + 2] = v.z;
    });
    
    // Faces (индексы)
    const indices = new Uint32Array(geometry.faces.flat());
    
    // Normals
    const normals = new Float32Array(geometry.normals.length * 3);
    geometry.normals.forEach((n, i) => {
      normals[i * 3] = n.x;
      normals[i * 3 + 1] = n.y;
      normals[i * 3 + 2] = n.z;
    });
    
    bufferGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    bufferGeometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
    bufferGeometry.setIndex(new THREE.BufferAttribute(indices, 1));
    
    // Материал
    const material = new THREE.MeshPhongMaterial({
      color: 0xd2b48c,
      side: THREE.DoubleSide,
      shininess: 100
    });
    
    // Меш
    const mesh = new THREE.Mesh(bufferGeometry, material);
    scene.add(mesh);
    
    // Автоматически расположить камеру на объект
    const box = new THREE.Box3().setFromObject(mesh);
    const center = box.getCenter(new THREE.Vector3());
    controls.target.copy(center);
    controls.autoRotate = true;
  };
  
  window.addEventListener('neural-cabinet-generated', handleNeuralGeneration as EventListener);
  
  return () => {
    window.removeEventListener('neural-cabinet-generated', handleNeuralGeneration as EventListener);
  };
}, [scene]);
```

## 🎯 Результат

После интеграции вы получите:

✅ **Новый режим "Neural Generator"** в приложении  
✅ **Параметр-контролируемая генерация 3D**  
✅ **Быстрая генерация** (1-3 сек)  
✅ **Детальная статистика** (вершины, грани, время, уверенность)  
✅ **Интеграция с 3D viewport** (опционально)  
✅ **Полностью offline** (после загрузки моделей)  

## 🧪 Тест интеграции

```typescript
// Тест в браузер консоли (F12)

// 1. Проверить, что модели загружены
window.localStorage.getItem('neural-models-loaded')
// должно быть: "true"

// 2. Проверить, что NeuralCADGenerator инициализирован
window.__neuralCADGenerator?.isReady()
// должно быть: true

// 3. Попробовать сгенерировать вручную
window.__neuralCADGenerator?.generate({
  width: 1200,
  height: 1400,
  depth: 600,
  shelfCount: 3,
  shelfThickness: 16,
  edgeType: 1,
  materialDensity: 800,
  hasDrawers: 0,
  drawerCount: 0,
  doorType: 1,
  baseType: 0,
  customFeatures: 0,
  quality: 0.85
}).then(result => {
  console.log('✅ Generated:', result.metrics);
});
```

---

**Готово!** 🎉 Нейросеть интегрирована и готова к использованию.
