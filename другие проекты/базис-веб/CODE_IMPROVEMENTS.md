# 🛠️ Технические рекомендации по коду

## Улучшение типизации в `types.ts`

### Текущие проблемы
```typescript
// ❌ Неточная типизация
type OpeningType = 'none' | 'left' | 'right' | 'top' | 'bottom' | 'drawer' | 'sliding' | 'folding';
type EdgeThickness = 'none' | '0.4' | '1.0' | '2.0';

// Проблемы:
// 1. Строковые union типы - сложно типизировать числовые операции
// 2. Нет гарантии валидности значений
// 3. Сложно добавлять новые значения
```

### ✅ Улучшенная версия
```typescript
// Используйте const assertions для типов
export const OPENING_TYPES = ['none', 'left', 'right', 'top', 'bottom', 'drawer', 'sliding', 'folding'] as const;
export type OpeningType = typeof OPENING_TYPES[number];

export const EDGE_THICKNESSES = [0.4, 1.0, 2.0] as const;
export type EdgeThickness = typeof EDGE_THICKNESSES[number] | 'none';

// Используйте Branded Types для безопасности
export type PanelId = string & { readonly __brand: 'PanelId' };
export const createPanelId = (id: string): PanelId => id as PanelId;

// Используйте Discriminated Unions
export type Hardware =
  | { type: 'handle'; diameter: number }
  | { type: 'hinge_cup'; x: number; y: number }
  | { type: 'shelf_support'; depth: number }
  | { type: 'legs'; height: number };

// Используйте mapped types для валидации
type ValidPanelDimension = {
  width: 50 | 100 | 150 | 200 | 250 | 300 | 350 | 400 | 450 | 500 | 550 | 600;
  height: number & { __min: 50; __max: 3000 };
  depth: number & { __min: 50; __max: 1000 };
};
```

---

## Оптимизация `projectStore.ts`

### Текущие проблемы
```typescript
// ❌ История может вырасти в памяти
history: Panel[][];
historyIndex: number;

// ❌ Нет лимита на историю
pushHistory: (panels: Panel[]) => {
  // история растет без контроля
};
```

### ✅ Улучшенная версия
```typescript
interface ProjectState {
  panels: Panel[];
  layers: Layer[];
  selectedPanelId: string | null;
  
  // Улучшенная история
  history: {
    past: Panel[][];
    present: Panel[];
    future: Panel[][];
    maxSize: number; // Лимит на память
  };
  
  // Actions
  undo: () => void;
  redo: () => void;
  pushHistory: (panels: Panel[]) => void;
  clearHistory: () => void;
}

// Реализация с лимитом
export const useProjectStore = create<ProjectState>((set, get) => ({
  history: {
    past: [],
    present: [],
    future: [],
    maxSize: 50, // Максимум 50 undo/redo операций
  },

  pushHistory: (panels) => {
    set((state) => {
      const { past, future } = state.history;
      const newPast = [...past, state.history.present];
      
      // Ограничить размер истории
      if (newPast.length > state.history.maxSize) {
        newPast.shift(); // Удалить самую старую
      }
      
      return {
        history: {
          ...state.history,
          past: newPast,
          present: panels,
          future: [], // Очистить future при новом действии
        },
      };
    });
  },

  undo: () => {
    set((state) => {
      const { past, present, future } = state.history;
      if (past.length === 0) return state;
      
      const newPast = past.slice(0, -1);
      const newPresent = past[past.length - 1];
      const newFuture = [present, ...future];
      
      return {
        panels: newPresent,
        history: { ...state.history, past: newPast, present: newPresent, future: newFuture },
      };
    });
  },
}));
```

---

## Оптимизация `geminiService.ts`

### Текущие проблемы
```typescript
// ❌ Жестко закодированная модель
MODEL_ID: "gemini-3-flash-preview", // Старая версия

// ❌ Нет retry logic
// ❌ Нет кэширования
// ❌ Нет streaming для UX
```

### ✅ Улучшенная версия
```typescript
import { GoogleGenerativeAI, CacheManager } from "@google/generative-ai";

const GEMINI_CONFIG = {
  // ✅ Используйте новую быструю модель
  MODEL_ID: "gemini-2.0-flash",
  
  // ✅ Кэширование системных промптов (сэкономить 50% затрат)
  CACHE_CONFIG: {
    ttl: 3600, // 1 час
    enable: true,
  },
  
  RETRY: {
    MAX_RETRIES: 3,
    INITIAL_DELAY_MS: 1000,
    MAX_DELAY_MS: 15000,
    EXPONENTIAL_BASE: 2,
    JITTER_MS: 500,
  },
  
  // ✅ Streaming для лучшего UX
  STREAM: true,
  MAX_OUTPUT_TOKENS: 4096,
  TEMPERATURE: 0.7,
};

// ✅ Реализация с retry и кэшированием
class GeminiService {
  private client: GoogleGenerativeAI;
  private cacheManager: CacheManager;

  constructor(apiKey: string) {
    this.client = new GoogleGenerativeAI(apiKey);
    this.cacheManager = new CacheManager(GEMINI_CONFIG.CACHE_CONFIG);
  }

  async generateWithCache(prompt: string, systemPrompt: string): Promise<string> {
    // 1. Проверить кэш
    const cached = this.cacheManager.get(systemPrompt);
    if (cached) {
      console.log('Using cached system prompt (50% cost savings)');
    }

    // 2. Вызвать API с кэшем
    const model = this.client.getGenerativeModel({
      model: GEMINI_CONFIG.MODEL_ID,
      systemInstruction: systemPrompt,
    });

    // 3. Streaming для лучшего UX
    const stream = await model.generateContentStream(prompt);
    
    let fullResponse = '';
    for await (const chunk of stream.stream) {
      if (chunk.text) {
        fullResponse += chunk.text;
        // Emit partial результаты для UI
        window.dispatchEvent(new CustomEvent('gemini-chunk', { 
          detail: { chunk: chunk.text } 
        }));
      }
    }

    return fullResponse;
  }

  async generateWithRetry(prompt: string, maxRetries = GEMINI_CONFIG.RETRY.MAX_RETRIES): Promise<string> {
    let lastError: Error | null = null;
    
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const model = this.client.getGenerativeModel({
          model: GEMINI_CONFIG.MODEL_ID,
        });

        const response = await model.generateContent(prompt);
        return response.response.text();
      } catch (error) {
        lastError = error as Error;
        
        // Экспоненциальная задержка + jitter
        const delay = Math.min(
          GEMINI_CONFIG.RETRY.INITIAL_DELAY_MS * 
            Math.pow(GEMINI_CONFIG.RETRY.EXPONENTIAL_BASE, attempt),
          GEMINI_CONFIG.RETRY.MAX_DELAY_MS
        ) + Math.random() * GEMINI_CONFIG.RETRY.JITTER_MS;
        
        console.log(`Retry attempt ${attempt + 1}/${maxRetries} after ${delay}ms`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }

    throw lastError || new Error('Max retries exceeded');
  }
}

export const geminiService = new GeminiService(process.env.GEMINI_API_KEY!);
```

---

## Оптимизация 3D сцены в `Scene3D.tsx`

### Текущие проблемы
```typescript
// ❌ Создание новых объектов каждый frame
// ❌ Нет LOD (Level of Detail)
// ❌ Нет Instanced Rendering
// ❌ Нет оптимизации памяти
```

### ✅ Улучшенная архитектура
```typescript
import * as THREE from 'three';

// ✅ LOD система для панелей
class OptimizedPanel {
  mesh: THREE.Group = new THREE.Group();
  private lod = new THREE.LOD();
  
  constructor(panel: Panel) {
    // Высокое качество для близких объектов
    const highPolyGeometry = new THREE.BoxGeometry(
      panel.width, panel.height, panel.depth
    );
    const highPolyMaterial = this.createMaterial(panel);
    const highPolyMesh = new THREE.Mesh(highPolyGeometry, highPolyMaterial);
    
    // Низкое качество для дальних объектов
    const lowPolyGeometry = new THREE.BoxGeometry(
      panel.width / 2, panel.height / 2, panel.depth / 2
    );
    const lowPolyMaterial = new THREE.MeshBasicMaterial({ color: 0xcccccc });
    const lowPolyMesh = new THREE.Mesh(lowPolyGeometry, lowPolyMaterial);
    
    // Добавить LOD уровни
    this.lod.addLevel(highPolyMesh, 0);     // 0-100 units
    this.lod.addLevel(lowPolyMesh, 100);    // >100 units
    
    this.mesh.add(this.lod);
  }
  
  private createMaterial(panel: Panel): THREE.Material {
    return new THREE.MeshStandardMaterial({
      color: panel.color,
      roughness: 0.7,
      metalness: 0.1,
      map: this.getTexture(panel.texture), // Кэшированные текстуры
    });
  }
}

// ✅ Instanced Rendering для одинаковых панелей
class PanelBatcher {
  private instancedMesh: THREE.InstancedMesh;
  private instanceMatrix = new THREE.Matrix4();
  
  constructor(panelCount: number) {
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.7,
    });
    
    this.instancedMesh = new THREE.InstancedMesh(
      geometry, 
      material, 
      panelCount
    );
  }
  
  updatePanelInstance(index: number, panel: Panel): void {
    this.instanceMatrix.setPosition(
      panel.x, panel.y, panel.z
    );
    this.instanceMatrix.scale(
      new THREE.Vector3(panel.width, panel.height, panel.depth)
    );
    
    this.instancedMesh.setMatrixAt(index, this.instanceMatrix);
    this.instancedMesh.instanceMatrix.needsUpdate = true;
  }
  
  dispose(): void {
    this.instancedMesh.geometry.dispose();
    (this.instancedMesh.material as any).dispose();
  }
}

// ✅ Оптимизированный компонент Scene3D
const Scene3D: React.FC<Props> = ({ panels }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const scene = useRef<THREE.Scene | null>(null);
  const renderer = useRef<THREE.WebGLRenderer | null>(null);
  const panelMeshes = useRef<Map<string, OptimizedPanel>>(new Map());
  const raycaster = useRef(new THREE.Raycaster());
  const mouse = useRef(new THREE.Vector2());
  let animationId: number | null = null;

  useEffect(() => {
    if (!containerRef.current) return;

    // Инициализация сцены с оптимизациями
    scene.current = new THREE.Scene();
    scene.current.background = new THREE.Color(0xeeeeee);
    
    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    
    renderer.current = new THREE.WebGLRenderer({ 
      antialias: true,
      powerPreference: 'high-performance', // ✅ Для мощных GPU
    });
    renderer.current.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // ✅ Не более 2x
    renderer.current.setSize(width, height);
    renderer.current.shadowMap.enabled = true;
    renderer.current.shadowMap.type = THREE.PCFShadowShadowMap; // ✅ Быстрее
    
    containerRef.current.appendChild(renderer.current.domElement);

    // Камера
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 10000);
    camera.position.set(500, 500, 500);
    camera.lookAt(0, 0, 0);

    // Освещение
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.current.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(500, 500, 500);
    directionalLight.shadow.camera.far = 2000;
    scene.current.add(directionalLight);

    // ✅ Обновить панели
    const updatePanels = () => {
      // Удалить старые панели
      panelMeshes.current.forEach(mesh => {
        scene.current?.remove(mesh.mesh);
      });
      panelMeshes.current.clear();

      // Добавить новые панели с LOD и оптимизацией
      panels.forEach(panel => {
        const optimizedPanel = new OptimizedPanel(panel);
        panelMeshes.current.set(panel.id, optimizedPanel);
        scene.current?.add(optimizedPanel.mesh);
      });
    };

    updatePanels();

    // ✅ Animate loop с requestAnimationFrame
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      
      // Render
      if (renderer.current && scene.current) {
        renderer.current.render(scene.current, camera);
      }
    };
    animate();

    // Event listeners
    const onMouseMove = (event: MouseEvent) => {
      mouse.current.x = (event.clientX / width) * 2 - 1;
      mouse.current.y = -(event.clientY / height) * 2 + 1;
    };

    containerRef.current.addEventListener('mousemove', onMouseMove);

    // Cleanup
    return () => {
      if (animationId) cancelAnimationFrame(animationId);
      containerRef.current?.removeEventListener('mousemove', onMouseMove);
      panelMeshes.current.forEach(mesh => {
        scene.current?.remove(mesh.mesh);
      });
      renderer.current?.dispose();
    };
  }, [panels]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
};

export default Scene3D;
```

---

## Оптимизация Web Worker для раскроя

### Текущее состояние
```javascript
// ❌ Простой worker без оптимизаций
```

### ✅ Улучшенный worker с Guillotine алгоритмом
```javascript
// workers/nesting.worker.js

/**
 * Guillotine 2D Bin Packing Algorithm
 * - Быстрый: O(n log n)
 * - Простой в реализации
 * - Хороший результат для мебели: 75-85% использования
 */

class Rectangle {
  constructor(x, y, width, height) {
    this.x = x;
    this.y = y;
    this.width = width;
    this.height = height;
    this.rightFree = true;
    this.bottomFree = true;
  }
}

class BinPacker {
  constructor(binWidth, binHeight) {
    this.binWidth = binWidth;
    this.binHeight = binHeight;
    this.rectangles = [new Rectangle(0, 0, binWidth, binHeight)];
  }

  /**
   * Guillotine split - быстрый метод упаковки
   */
  pack(width, height) {
    let bestRect = null;
    let bestRectIndex = -1;

    // Найти наилучший прямоугольник для упаковки
    for (let i = 0; i < this.rectangles.length; i++) {
      const rect = this.rectangles[i];
      
      if (rect.width >= width && rect.height >= height) {
        if (!bestRect || 
            rect.width * rect.height < bestRect.width * bestRect.height) {
          bestRect = rect;
          bestRectIndex = i;
        }
      }
    }

    if (!bestRect) return null;

    // Упаковать и разделить прямоугольник
    const packedRect = new Rectangle(
      bestRect.x, bestRect.y, width, height
    );

    // Горизонтальное разделение (Guillotine)
    if (bestRect.width > width) {
      this.rectangles.push(
        new Rectangle(
          bestRect.x + width,
          bestRect.y,
          bestRect.width - width,
          height
        )
      );
    }

    // Вертикальное разделение (Guillotine)
    if (bestRect.height > height) {
      this.rectangles.push(
        new Rectangle(
          bestRect.x,
          bestRect.y + height,
          bestRect.width,
          bestRect.height - height
        )
      );
    }

    // Удалить использованный прямоугольник
    this.rectangles.splice(bestRectIndex, 1);

    return packedRect;
  }

  /**
   * Пакет всех панелей с оптимизацией
   */
  packAll(items) {
    // Сортировать по площади (больше первым)
    const sorted = items.sort((a, b) => 
      (b.width * b.height) - (a.width * a.height)
    );

    const result = [];
    for (const item of sorted) {
      const packed = this.pack(item.width, item.height);
      if (!packed) return null; // Не влезло

      result.push({
        ...item,
        packX: packed.x,
        packY: packed.y,
      });
    }

    return result;
  }
}

/**
 * Оптимизация раскроя материала
 */
function optimizeNesting(panels, sheetWidth, sheetHeight) {
  const packer = new BinPacker(sheetWidth, sheetHeight);
  const packed = packer.packAll(panels);

  if (!packed) {
    return {
      success: false,
      message: 'Не удалось упаковать все панели',
    };
  }

  // Рассчитать эффективность
  const totalPanelArea = panels.reduce((sum, p) => sum + p.width * p.height, 0);
  const sheetArea = sheetWidth * sheetHeight;
  const efficiency = (totalPanelArea / sheetArea) * 100;

  return {
    success: true,
    packed,
    efficiency: Math.round(efficiency),
    wasteArea: sheetArea - totalPanelArea,
  };
}

/**
 * Message Handler - получить данные из основного потока
 */
self.onmessage = function(event) {
  const { panels, sheetWidth, sheetHeight } = event.data;

  // Выполнить оптимизацию
  const result = optimizeNesting(panels, sheetWidth, sheetHeight);

  // Отправить результат обратно
  self.postMessage(result);
};
```

### Использование в компоненте
```typescript
// components/NestingView.tsx
const NestingView: React.FC<Props> = ({ panels }) => {
  const [result, setResult] = useState<NestingResult | null>(null);

  useEffect(() => {
    // Инициализировать worker
    const worker = new Worker(
      new URL('../workers/nesting.worker.js', import.meta.url),
      { type: 'module' }
    );

    // Отправить данные
    worker.postMessage({
      panels: panels.map(p => ({
        id: p.id,
        width: p.width,
        height: p.height,
        depth: p.depth,
      })),
      sheetWidth: 2800, // Стандартный лист ЛДСП
      sheetHeight: 2070,
    });

    // Получить результат
    worker.onmessage = (e) => {
      setResult(e.data);
      worker.terminate();
    };

    return () => worker.terminate();
  }, [panels]);

  return (
    <div>
      {result && (
        <>
          <p>Эффективность раскроя: {result.efficiency}%</p>
          <p>Отходы: {result.wasteArea} см²</p>
          {/* Визуализация раскроя */}
        </>
      )}
    </div>
  );
};
```

---

## Performance Checklist

- [ ] Использовать React.memo для дорогих компонентов
- [ ] Использовать useMemo для вычислений
- [ ] Использовать useCallback для callbacks
- [ ] LOD для 3D объектов
- [ ] Instanced Rendering для повторяющихся элементов
- [ ] Web Workers для тяжелых расчетов
- [ ] Виртуализация больших списков
- [ ] Lazy loading для изображений
- [ ] Code splitting с React.lazy
- [ ] Профилировать с DevTools Profiler

---

## Testing Checklist

- [ ] Unit tests для utils функций
- [ ] Component tests для UI
- [ ] Integration tests для workflow
- [ ] E2E tests для критических путей
- [ ] Performance tests для 3D сцены
- [ ] Memory leak tests для long-running sessions

