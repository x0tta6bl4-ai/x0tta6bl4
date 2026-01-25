# ПРИМЕНЕНИЕ BEST PRACTICES К БАЗИС-ВЕБ

**Дата:** 18 января 2026  
**Цель:** Как трансформировать текущую архитектуру в профессиональную CAD систему

---

## 🎯 ТЕКУЩЕЕ СОСТОЯНИЕ vs ЦЕЛЕВОЕ

### Текущая архитектура (Базис-веб сейчас)

```
Scene3D.tsx
├── Scene3DRenderer.ts (Three.js setup)
├── Scene3DMesh.ts (Geometry management)
├── Scene3DMaterial.ts (Materials)
└── projectStore.ts (Zustand state)
    └── panels: Panel[]  ❌ просто массив, без истории
```

**Проблемы:**
- ✗ Нет history/undo-redo
- ✗ Нет параметрического моделирования (изменил размер → пересчет)
- ✗ Нет LOD системы для большого кол-ва панелей
- ✗ Нет Web Workers для расчетов
- ✗ Нет real-time синхронизации

### Целевая архитектура (как Fusion 360)

```
┌─────────────────────────────────────┐
│     React Components                 │
│  (Scene3D, ParametricEditor, etc)    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     CAD Document Model               │
│  (Feature Tree, Constraints)         │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     Geometry Engine                  │
│  (Boolean ops, Mesh generation)      │
│  (Может быть в Web Worker)          │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     Rendering Layer (Three.js)      │
│  (LOD, Instancing, Culling)         │
└─────────────────────────────────────┘
```

---

## 📋 ПЛАН ВНЕДРЕНИЯ (4 НЕДЕЛИ)

### НЕДЕЛЯ 1: Feature Tree + Command Pattern

**Файл: store/cadModel.ts** - новый документ модель

```typescript
// ============ НОВЫЙ ФАЙЛ: store/cadModel.ts ============

export interface Feature {
  id: string;
  name: string;
  type: 'sketch' | 'pad' | 'assembly';
  
  // Параметры фичи
  parameters: Record<string, any>;
  
  // Зависимости
  dependsOn: string[];
  
  // Для пересчета
  cached?: boolean;
  cachedGeometry?: THREE.BufferGeometry;
}

export class CADDocument {
  id: string = generateUUID();
  name: string = 'Untitled';
  
  // Feature tree - история операций
  features: Feature[] = [];
  
  // Где хранится текущее состояние (для быстрого доступа)
  panels: Panel[] = [];
  
  // История команд (для undo/redo)
  history: Command[] = [];
  historyIndex: number = -1;

  // Добавить фичу
  addFeature(feature: Feature) {
    this.features.push(feature);
    this.invalidateCache(feature.id);
    this.rebuildGeometry();
  }

  // Пересчитать кэш фичи
  private invalidateCache(featureId: string) {
    // Mark all dependent features as invalid
    for (const feat of this.features) {
      if (feat.dependsOn?.includes(featureId)) {
        feat.cached = false;
        this.invalidateCache(feat.id);
      }
    }
  }

  // Пересчитать всю геометрию
  private rebuildGeometry() {
    for (const feature of this.features) {
      if (!feature.cached) {
        // Пересчитать эту фичу
        // Это может быть в Web Worker
        this.computeFeatureGeometry(feature);
        feature.cached = true;
      }
    }
  }

  private computeFeatureGeometry(feature: Feature) {
    switch (feature.type) {
      case 'sketch':
        // Просто абстрактный sketch
        break;
      case 'pad':
        // Экструзия sketch на глубину
        const depth = feature.parameters.depth;
        const sketchId = feature.dependsOn[0];
        
        // Здесь был бы расчет булевой операции
        // но у нас упрощенная версия - просто box
        const panel = this.createPadPanel(feature, depth);
        break;
    }
  }

  private createPadPanel(feature: Feature, depth: number): Panel {
    return {
      id: feature.id,
      name: feature.name,
      width: feature.parameters.width,
      height: feature.parameters.height,
      depth: depth,
      x: 0,
      y: 0,
      z: 0,
      rotation: 'Z',
      // ... остальные поля
    };
  }
}

// ============ ОБНОВИТЬ: store/projectStore.ts ============

export interface ProjectState {
  // НОВОЕ: сам документ CAD
  cadDocument: CADDocument;
  
  // История команд
  commandHistory: CommandHistory;
  
  // Actions
  executeCommand: (command: Command) => void;
  undo: () => void;
  redo: () => void;
  addPad: (sketchId: string, depth: number) => void;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  cadDocument: new CADDocument(),
  commandHistory: new CommandHistory(),

  executeCommand: (command) => {
    get().commandHistory.execute(command);
    // Триггерить re-render
    set(state => ({ cadDocument: { ...state.cadDocument } }));
  },

  undo: () => {
    get().commandHistory.undo();
    set(state => ({ cadDocument: { ...state.cadDocument } }));
  },

  redo: () => {
    get().commandHistory.redo();
    set(state => ({ cadDocument: { ...state.cadDocument } }));
  },

  addPad: (sketchId, depth) => {
    const command = new CreatePadCommand(get().cadDocument, sketchId, depth);
    get().executeCommand(command);
  }
}));
```

**Файл: services/commands.ts** - Command Pattern

```typescript
export abstract class Command {
  abstract execute(): void;
  abstract undo(): void;
  abstract redo(): void;
}

export class CreatePadCommand extends Command {
  constructor(
    private doc: CADDocument,
    private sketchId: string,
    private depth: number
  ) { super(); }

  execute() {
    const feature: Feature = {
      id: generateUUID(),
      name: `Pad of ${this.sketchId}`,
      type: 'pad',
      parameters: { depth: this.depth },
      dependsOn: [this.sketchId]
    };

    this.doc.addFeature(feature);
  }

  undo() {
    // Удалить фичу и пересчитать
    this.doc.features = this.doc.features.filter(
      f => f.name !== `Pad of ${this.sketchId}`
    );
    this.doc.rebuildGeometry();
  }

  redo() {
    this.execute();
  }
}

export class CommandHistory {
  private stack: Command[] = [];
  private index: number = -1;

  execute(command: Command) {
    // Если были undo - удалить redo
    this.stack = this.stack.slice(0, this.index + 1);
    
    command.execute();
    this.stack.push(command);
    this.index++;
  }

  undo() {
    if (this.index >= 0) {
      this.stack[this.index].undo();
      this.index--;
    }
  }

  redo() {
    if (this.index < this.stack.length - 1) {
      this.index++;
      this.stack[this.index].redo();
    }
  }

  get canUndo() { return this.index >= 0; }
  get canRedo() { return this.index < this.stack.length - 1; }
}
```

### НЕДЕЛЯ 2: LOD System + Instancing

**Файл: services/Scene3DLOD.ts**

```typescript
export class LODManager {
  private lodLevels = [
    { distance: 0,    simplification: 1.0,  label: 'HD' },
    { distance: 50,   simplification: 0.5,  label: 'High' },
    { distance: 200,  simplification: 0.2,  label: 'Medium' },
    { distance: 500,  simplification: 0.05, label: 'Low' },
  ];

  private cache = new Map<string, THREE.BufferGeometry[]>();

  getMesh(panelId: string, geometry: THREE.BufferGeometry, cameraDistance: number): THREE.BufferGeometry {
    const key = panelId + ':' + cameraDistance;

    // Выбрать уровень детализации
    const lod = this.lodLevels.find(l => cameraDistance > l.distance)
             || this.lodLevels[this.lodLevels.length - 1];

    // Использовать кэш
    if (!this.cache.has(panelId)) {
      const levels = this.generateLODLevels(geometry);
      this.cache.set(panelId, levels);
    }

    const levels = this.cache.get(panelId)!;
    const levelIndex = this.lodLevels.indexOf(lod);

    return levels[levelIndex];
  }

  private generateLODLevels(geometry: THREE.BufferGeometry): THREE.BufferGeometry[] {
    return this.lodLevels.map(lod => {
      // Использовать Simplification.js или похожую библиотеку
      return this.simplifyGeometry(geometry, lod.simplification);
    });
  }

  private simplifyGeometry(geometry: THREE.BufferGeometry, ratio: number): THREE.BufferGeometry {
    // Упрощение геометрии (например, через Simplification.js)
    // Для MVP можно просто вернуть оригинальную
    return geometry;
  }
}

export class InstancedMeshManager {
  // Для визуализации одинаковых деталей (скажем, 100 шурупов)
  createInstancedMesh(baseGeometry: THREE.BufferGeometry, material: THREE.Material, count: number): THREE.InstancedMesh {
    const mesh = new THREE.InstancedMesh(baseGeometry, material, count);
    
    const dummy = new THREE.Object3D();

    for (let i = 0; i < count; i++) {
      dummy.position.set(i * 10, 0, 0); // Пример позиции
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }

    mesh.instanceMatrix.needsUpdate = true;
    return mesh;
  }
}
```

### НЕДЕЛЯ 3: Web Workers для расчетов

**Файл: workers/geometryWorker.ts**

```typescript
// Работает в отдельном потоке - не блокирует UI!

self.onmessage = (event: MessageEvent) => {
  const { type, data } = event.data;

  if (type === 'simplifyGeometry') {
    // Тяжелый расчет упрощения геометрии
    const simplified = simplifyGeometry(data.geometry, data.ratio);
    
    self.postMessage({
      type: 'simplifyGeometryResult',
      result: simplified
    });
  }

  if (type === 'boolean') {
    // Boolean операции (Union, Intersection, Difference)
    // Здесь могут быть вызовы OCCT.js
    const result = performBooleanOp(data.geometry1, data.geometry2, data.operation);
    
    self.postMessage({
      type: 'booleanResult',
      result: result
    });
  }
};
```

**Файл: services/geometryWorker.ts** - управление worker

```typescript
export class GeometryWorkerPool {
  private worker: Worker;

  constructor() {
    // Инициализировать worker
    if (typeof window !== 'undefined') {
      this.worker = new Worker(
        new URL('../workers/geometryWorker.ts', import.meta.url),
        { type: 'module' }
      );
    }
  }

  simplifyGeometry(geometry: THREE.BufferGeometry, ratio: number): Promise<THREE.BufferGeometry> {
    return new Promise((resolve) => {
      const handler = (event: MessageEvent) => {
        if (event.data.type === 'simplifyGeometryResult') {
          this.worker.removeEventListener('message', handler);
          resolve(event.data.result);
        }
      };

      this.worker.addEventListener('message', handler);
      this.worker.postMessage({
        type: 'simplifyGeometry',
        data: {
          geometry: geometry.toJSON(),
          ratio: ratio
        }
      });
    });
  }
}
```

### НЕДЕЛЯ 4: Real-time Sync (WebSocket)

**Файл: services/syncService.ts**

```typescript
import io from 'socket.io-client';

export class SyncService {
  private socket: ReturnType<typeof io>;

  constructor(private documentId: string) {
    this.socket = io(`/documents/${documentId}`);

    // При подключении
    this.socket.on('connect', () => {
      console.log('Connected to sync server');
    });

    // Получить изменение от другого пользователя
    this.socket.on('remoteOperation', (operation: Command) => {
      // Применить операцию
      useProjectStore.getState().executeCommand(operation);
    });

    // Получить конфликт
    this.socket.on('conflict', (resolution) => {
      // CRDT разрешит конфликт автоматически
      applyResolution(resolution);
    });
  }

  // Отправить свою операцию другим пользователям
  broadcastOperation(command: Command) {
    this.socket.emit('operation', {
      command: command,
      userId: getCurrentUserId(),
      timestamp: Date.now()
    });
  }

  disconnect() {
    this.socket.disconnect();
  }
}
```

---

## 🚀 БЫСТРЫЙ СТАРТ (ДО КОНЦА НЕДЕЛИ)

### Минимальные изменения для Undo/Redo прямо сейчас:

**1. Добавить CommandHistory в projectStore.ts**

```typescript
// В useProjectStore:
commandHistory: [] as Command[],
historyIndex: -1,

updatePanel: (id, changes) => {
  const oldPanel = get().panels.find(p => p.id === id);
  if (!oldPanel) return;

  // Создать команду
  const command = {
    id: generateUUID(),
    type: 'updatePanel',
    panelId: id,
    oldChanges: { ...oldPanel },
    newChanges: changes,
    
    execute: () => {
      set(state => ({
        panels: state.panels.map(p => p.id === id ? { ...p, ...changes } : p)
      }));
    },
    
    undo: () => {
      set(state => ({
        panels: state.panels.map(p => p.id === id ? oldPanel : p)
      }));
    }
  };

  // Добавить в историю
  const history = get().commandHistory;
  const newHistory = history.slice(0, get().historyIndex + 1);
  newHistory.push(command);
  
  set({ 
    commandHistory: newHistory,
    historyIndex: newHistory.length - 1
  });

  command.execute();
},

undo: () => {
  const { commandHistory, historyIndex } = get();
  if (historyIndex >= 0) {
    commandHistory[historyIndex].undo?.();
    set({ historyIndex: historyIndex - 1 });
  }
},

redo: () => {
  const { commandHistory, historyIndex } = get();
  if (historyIndex < commandHistory.length - 1) {
    set({ historyIndex: historyIndex + 1 });
    commandHistory[historyIndex + 1].execute?.();
  }
}
```

**2. Добавить кнопки Undo/Redo в UI**

```tsx
// В Scene3D.tsx или ToolbarControls.tsx

const { canUndo, canRedo, undo, redo } = useProjectStore();

<button 
  onClick={undo}
  disabled={!canUndo}
  title="Ctrl+Z"
>
  ↶ Undo
</button>

<button 
  onClick={redo}
  disabled={!canRedo}
  title="Ctrl+Y"
>
  ↷ Redo
</button>

// Клавиатурные сокращения
useEffect(() => {
  const handleKeydown = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
      e.preventDefault();
      undo();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
      e.preventDefault();
      redo();
    }
  };

  window.addEventListener('keydown', handleKeydown);
  return () => window.removeEventListener('keydown', handleKeydown);
}, [undo, redo]);
```

---

## 📊 МЕТРИКИ УЛУЧШЕНИЯ

| Метрика | Текущее | Целевое | Статус |
|---------|---------|---------|--------|
| Undo/Redo | ❌ Нет | ✅ Да | Неделя 1 |
| Max панелей на сцене | ~100 | 10000+ | Неделя 2 |
| Load time для 1000 панелей | N/A | <500ms | Неделя 2-3 |
| UI freeze при расчетах | N/A | 0ms | Неделя 3 |
| Multi-user edit | ❌ Нет | ✅ Да | Неделя 4 |
| Conflict resolution | N/A | ✅ Auto | Неделя 4 |

---

## ✅ ЧЕК-ЛИСТ РЕАЛИЗАЦИИ

- [ ] **Неделя 1**
  - [ ] CADDocument class в store/cadModel.ts
  - [ ] Command abstract class
  - [ ] CreatePadCommand implementation
  - [ ] CommandHistory с undo/redo
  - [ ] Undo/Redo UI buttons

- [ ] **Неделя 2**
  - [ ] LODManager для упрощения геометрии
  - [ ] InstancedMeshManager для одинаковых деталей
  - [ ] Тест с 1000+ панелями
  - [ ] Профилирование производительности

- [ ] **Неделя 3**
  - [ ] Web Worker для геometryWorker.ts
  - [ ] GeometryWorkerPool wrapper
  - [ ] Простая Boolean операция в worker
  - [ ] Измерить улучшение performance

- [ ] **Неделя 4**
  - [ ] WebSocket integrация (Socket.io)
  - [ ] Broadcast операций
  - [ ] Простой CRDT для конфликтов
  - [ ] Multi-user тест

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

- [Three.js Performance Tips](https://threejs.org/docs/#manual/en/introduction/How-to-dispose-of-objects)
- [CRDT Algorithms](https://crdt.tech/)
- [Fusion 360 Architecture](https://forums.autodesk.com/t5/fusion-360-design-validate/The-overall-architecture-of-Fusion-360/m-p/9685398)
- [OCP (Open Cascade)](https://dev.opencascade.org/)

Начните с Недели 1 прямо сейчас - это займет ~4 часа!
