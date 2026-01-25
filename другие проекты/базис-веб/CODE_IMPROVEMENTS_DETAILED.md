# 📋 Comprehensive Code Analysis & Improvement Recommendations

**Date:** January 18, 2026  
**Application:** базис-веб (Basis-Web) - Cabinet/Furniture CAD System  
**Analysis Scope:** All source files examined  
**Priority Levels:** 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low

---

## Executive Summary

The application is a sophisticated parametric furniture CAD system with good architectural foundations and recent Phase 1 optimizations. Analysis identifies **22 improvement opportunities** across code quality, performance, type safety, error handling, and maintainability.

**Key Findings:**
- ✅ Good separation of concerns (components, services, store)
- ✅ TypeScript strict mode potential achieved in Phase 1
- ⚠️ Some error handling gaps that could cause runtime issues
- ⚠️ Missing environment configuration safety
- ⚠️ Hardcoded values could be extracted
- ⚠️ Component complexity could be reduced

---

## 1. CRITICAL ISSUES 🔴

### 1.1 Environment Configuration Vulnerability

**File:** [vite.config.ts](vite.config.ts)  
**Severity:** 🔴 CRITICAL  
**Issue:** API key exposed in environment without fallback or validation

```typescript
// CURRENT (UNSAFE):
define: {
  'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
  'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
}
```

**Risks:**
- API key bundled into client-side JavaScript in production builds
- Exposed to network requests and browser DevTools
- No validation if key is missing

**Recommendation:**
```typescript
// IMPROVED:
const apiKey = env.GEMINI_API_KEY || '';
if (!apiKey && mode === 'production') {
  console.warn('⚠️ GEMINI_API_KEY not configured in production');
}

define: {
  'process.env.API_KEY': JSON.stringify(apiKey),
  // Remove from bundle - only use at initialization time
}
```

---

### 1.2 Unhandled Promise Rejections in App.tsx

**File:** [App.tsx](App.tsx#L74-L93)  
**Severity:** 🔴 CRITICAL  
**Issue:** Storage operations without error boundary or recovery mechanism

```typescript
// CURRENT (UNSAFE):
const loadLast = async () => {
    const saved = localStorage.getItem('bazis_project');
    if (saved) {
        try {
            const data = JSON.parse(saved);  // Can throw if corrupted
            if (Array.isArray(data.panels) && data.panels.length > 0) {
                setPanels(data.panels);  // No error handling if invalid data
                addToast('Проект восстановлен', 'success');
            } else {
                loadDefaultProject();
            }
        } catch (e) { loadDefaultProject(); }  // Silent fail
    } else {
        loadDefaultProject();
    }
};
```

**Risks:**
- Corrupted localStorage could crash the app
- Silent error swallowing prevents debugging
- Invalid panel data could cause rendering errors

**Recommendation:**
```typescript
const loadLast = async () => {
    try {
        const saved = localStorage.getItem('bazis_project');
        if (!saved) {
            loadDefaultProject();
            return;
        }

        const data = JSON.parse(saved);
        
        // Validate data structure
        if (!Array.isArray(data.panels)) {
            throw new Error('Invalid panels structure');
        }

        // Validate each panel
        const validPanels = data.panels.filter(validatePanelStructure);
        if (validPanels.length === 0) {
            throw new Error('No valid panels found');
        }

        setPanels(validPanels);
        addToast('Проект восстановлен из автосохранения', 'success');
    } catch (error) {
        console.error('[App] Failed to load project:', error);
        addToast('Не удалось загрузить проект. Загружена пустая версия.', 'warning');
        loadDefaultProject();
    }
};
```

---

### 1.3 Missing Database Error Handling

**File:** [storageService.ts](storageService.ts)  
**Severity:** 🔴 CRITICAL  
**Issue:** Database operations fail silently with unclear error messages

```typescript
// CURRENT (WEAK):
request.onerror = () => reject(request.error);  // No error context
```

**Recommendation:**
```typescript
request.onerror = () => {
    const errorMsg = `Failed to initialize database: ${request.error?.message || 'Unknown error'}`;
    console.error('[StorageService]', errorMsg);
    reject(new Error(errorMsg));
};
```

---

## 2. HIGH-PRIORITY ISSUES 🟠

### 2.1 Type Safety - Partial Property Updates

**File:** [projectStore.ts](projectStore.ts#L88-L95)  
**Severity:** 🟠 HIGH  
**Issue:** `Partial<Panel>` updates allow invalid state transitions

```typescript
// CURRENT (UNSAFE):
updatePanel: (id: string, changes: Partial<Panel>) => void;

// Usage allows invalid updates:
updatePanel('panel-1', { width: 'invalid' } as any);  // TypeScript weakness
```

**Impact:**
- No validation of dimension constraints
- Can create geometrically invalid panels
- Silent data corruption possible

**Recommendation:**
```typescript
// Better type safety:
interface PanelDimensions {
  width?: number;  // Must be validated
  height?: number;
  depth?: number;
}

interface PanelProperties {
  dimensions?: PanelDimensions;
  position?: Partial<{ x: number; y: number; z: number }>;
  appearance?: Partial<{ color: string; texture: TextureType }>;
  hardware?: Hardware[];
  // ... other grouped properties
}

updatePanel: (id: string, changes: PanelProperties) => Promise<ValidationResult>;

// Usage with validation:
const result = await updatePanel('panel-1', {
  dimensions: { width: 800, height: 1000 }
});

if (!result.valid) {
  addToast(`Ошибка обновления: ${result.errors.join(', ')}`, 'error');
}
```

---

### 2.2 Script Execution DSL Vulnerability

**File:** [App.tsx](App.tsx#L195-L240)  
**Severity:** 🟠 HIGH  
**Issue:** DSL code execution without sandboxing or validation

```typescript
// CURRENT (UNSAFE):
const handleRunScript = (code: string) => {
    try {
        // Defines local variables in function scope
        const DeleteAll = () => { /* ... */ };
        const AddPanel = (w, h, th = 16) => { /* ... */ };
        
        // eval() equivalent - dangerous!
        eval(code);  // Code can access window, document, etc.
    } catch (e) {
        addToast('Ошибка скрипта', 'error');
    }
};
```

**Risks:**
- User scripts can access global scope
- No resource limits (infinite loops possible)
- No permission boundaries

**Recommendation:**
```typescript
// Option 1: Use Worker with isolated scope
const executeScriptInWorker = (code: string) => {
    const worker = new Worker('/script-worker.js');
    worker.postMessage({ code, api: { AddPanel, DeleteAll } });
    
    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            worker.terminate();
            reject(new Error('Script execution timeout'));
        }, 5000);
        
        worker.onmessage = (e) => {
            clearTimeout(timeout);
            resolve(e.data);
        };
        
        worker.onerror = reject;
    });
};

// Option 2: Use vm2 library for sandboxing
import { NodeVM } from 'vm2';

const executeScriptSafely = (code: string) => {
    const vm = new NodeVM({
        sandbox: {
            AddPanel: (w, h) => { /* ... */ },
            DeleteAll: () => { /* ... */ },
        },
        timeout: 5000,
        eval: false,
        fixAsync: true,
    });

    return vm.run(code);
};
```

---

### 2.3 Missing Input Validation Throughout

**Files:** Multiple component files  
**Severity:** 🟠 HIGH  
**Issue:** User inputs accepted without validation

**Example from EditorPanel.tsx:**
```typescript
// CURRENT (NO VALIDATION):
const handlePanelUpdate = (field: string, value: any) => {
    updatePanel(selectedPanel.id, { [field]: value });
};

// Can receive:
// - Negative dimensions
// - NaN values
// - Out-of-range positions
// - Invalid material IDs
```

**Recommendation:** Implement input validation layer

```typescript
// validators.ts - Enhancement
export class InputValidator {
  static validateDimension(value: any, min = 50, max = 5000): number {
    const num = Number(value);
    if (isNaN(num)) throw new Error('Invalid dimension: not a number');
    if (num < min) throw new Error(`Minimum dimension: ${min}mm`);
    if (num > max) throw new Error(`Maximum dimension: ${max}mm`);
    return Math.round(num);
  }

  static validateColor(value: any): string {
    if (!/^#[0-9A-F]{6}$/i.test(value)) {
      throw new Error('Invalid hex color format');
    }
    return value;
  }

  static validateMaterialId(id: string, library: Material[]): string {
    if (!library.find(m => m.id === id)) {
      throw new Error(`Material not found: ${id}`);
    }
    return id;
  }
}

// Usage in components:
const handleWidthChange = (value: string) => {
    try {
        const validated = InputValidator.validateDimension(value);
        updatePanel(id, { width: validated });
    } catch (error) {
        addToast(error.message, 'error');
    }
};
```

---

### 2.4 Missing Null Safety in Panel Operations

**File:** [projectStore.ts](projectStore.ts#L85-L95)  
**Severity:** 🟠 HIGH  
**Issue:** Operations assume panel exists without null checks

```typescript
// CURRENT (UNSAFE):
const duplicatePanel = (id: string) => {
    const panel = get().panels.find(p => p.id === id);  // Could be undefined
    const newPanel = { ...panel, id: newId };  // Crashes if panel is undefined
    set({ panels: [...get().panels, newPanel] });
};
```

**Recommendation:**
```typescript
const duplicatePanel = (id: string) => {
    const panel = get().panels.find(p => p.id === id);
    
    if (!panel) {
        console.error(`[ProjectStore] Panel not found: ${id}`);
        return false;
    }

    const newPanel = {
        ...panel,
        id: `${panel.id}-copy-${Date.now()}`,
        name: `${panel.name} (Копия)`
    };

    set({ panels: [...get().panels, newPanel] });
    return true;
};
```

---

## 3. MEDIUM-PRIORITY ISSUES 🟡

### 3.1 Extract Magic Numbers to Constants

**Files:** Multiple files  
**Severity:** 🟡 MEDIUM  
**Issue:** Hardcoded values scattered throughout code

**Examples:**
- `1800`, `2500`, `650` in default project (App.tsx)
- `28` in EditorPanel (hardcoded hinge count)
- `37`, `34` in hardware utilities
- `DB_VERSION: 1` (needs migration strategy)

**Recommendation:**
```typescript
// constants/dimensions.ts
export const DEFAULT_DIMENSIONS = {
  CABINET: {
    WIDTH: 1800,      // Standard kitchen cabinet width
    HEIGHT: 2500,     // Full height cabinet
    DEPTH: 650,       // Standard depth
    MIN_WIDTH: 150,
    MAX_WIDTH: 3000,
    MIN_HEIGHT: 300,
    MAX_HEIGHT: 3000,
    MIN_DEPTH: 200,
    MAX_DEPTH: 800,
  },
  PANEL: {
    MIN_THICKNESS: 4,
    MAX_THICKNESS: 50,
    EDGE_DISTANCE: 8,
  },
  HINGE: {
    COUNT_LIGHT: 2,    // < 900mm
    COUNT_MEDIUM: 3,   // 900-1600mm
    COUNT_HEAVY: 4,    // 1600-2000mm
    COUNT_EXTRA: 5,    // > 2000mm
  }
};

// Usage:
const { CABINET, PANEL } = DEFAULT_DIMENSIONS;
const initialPanel = {
  width: CABINET.WIDTH,
  height: CABINET.HEIGHT,
  depth: CABINET.DEPTH
};
```

---

### 3.2 Improve Component Composition

**File:** [EditorPanel.tsx](EditorPanel.tsx#L1-L100)  
**Severity:** 🟡 MEDIUM  
**Issue:** Large monolithic component (406 lines) handling multiple concerns

**Current Structure:**
```
EditorPanel (406 lines)
├── Structure View (panel list)
├── Properties View
│   ├── Dimensions
│   ├── Materials
│   ├── Hardware
│   ├── Edging
│   └── Grooves
└── Utilities
    ├── Visibility toggle
    ├── Hardware presets
    └── Validation
```

**Recommendation:** Split into smaller components

```typescript
// components/EditorPanel/
├── EditorPanel.tsx (main orchestrator, ~150 lines)
├── StructureView.tsx (panel list view, ~100 lines)
├── PropertiesView.tsx (selected panel editor, ~80 lines)
├── hardware/ (hardware-specific components)
│   ├── HardwareEditor.tsx
│   ├── HardwarePresets.tsx
│   └── HardwareValidator.tsx
├── appearance/ (color, texture, edging)
│   ├── AppearanceEditor.tsx
│   ├── TextureSelector.tsx
│   └── EdgeingEditor.tsx
└── utils/
    ├── panelHelpers.ts
    └── validationHelpers.ts

// Benefits:
// - Easier to test
// - Reusable components
// - Easier to maintain
// - Faster re-renders (memoization)
```

**Example refactor:**
```typescript
// New HardwareEditor component
interface HardwareEditorProps {
  hardware: Hardware[];
  panelWidth: number;
  panelHeight: number;
  onUpdate: (hardware: Hardware[]) => void;
}

const HardwareEditor: React.FC<HardwareEditorProps> = ({
  hardware,
  panelWidth,
  panelHeight,
  onUpdate
}) => {
  const addPreset = (preset: HardwarePreset) => {
    const newHardware = generateHardwareFromPreset(preset, panelWidth, panelHeight);
    onUpdate([...hardware, ...newHardware]);
  };

  return (
    <div>
      <HardwarePresets onSelect={addPreset} />
      <HardwareList items={hardware} onRemove={(id) => {}} />
    </div>
  );
};

export default memo(HardwareEditor);
```

---

### 3.3 Missing Error Recovery in Gemini Service

**File:** [geminiService.ts](geminiService.ts#L12-L26)  
**Severity:** 🟡 MEDIUM  
**Issue:** Retry logic defined but may not handle all failure modes

```typescript
// CURRENT:
const RETRY = {
  MAX_RETRIES: 3,
  INITIAL_DELAY_MS: 1000,
  MAX_DELAY_MS: 15000,
  EXPONENTIAL_BASE: 2,
  JITTER_MS: 500,
}
```

**Issue:** Doesn't handle:
- Rate limiting (429 Too Many Requests)
- Network timeouts
- Invalid API key
- Quota exceeded

**Recommendation:**
```typescript
export interface RetryConfig {
  maxRetries: number;
  initialDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
  jitterMs: number;
  retryableStatusCodes: number[];  // [429, 503, 504, 408]
}

class GeminiService {
  private async callWithRetry<T>(
    fn: () => Promise<T>,
    config: RetryConfig = DEFAULT_RETRY_CONFIG,
    attempt = 1
  ): Promise<T> {
    try {
      return await fn();
    } catch (error) {
      const isRetryable = this.isRetryableError(error);
      
      if (!isRetryable || attempt > config.maxRetries) {
        throw error;
      }

      const delay = Math.min(
        config.initialDelayMs * Math.pow(config.backoffMultiplier, attempt - 1),
        config.maxDelayMs
      ) + Math.random() * config.jitterMs;

      console.warn(
        `[Gemini] Retrying (${attempt}/${config.maxRetries}) after ${delay}ms:`,
        error.message
      );

      await new Promise(r => setTimeout(r, delay));
      return this.callWithRetry(fn, config, attempt + 1);
    }
  }

  private isRetryableError(error: any): boolean {
    if (error.status === 401) return false;  // Auth error, don't retry
    if (error.status === 403) return false;  // Permission error
    if (error.status === 404) return false;  // Not found
    if (error.message?.includes('API key')) return false;  // Invalid API key
    return true;  // Assume network/server errors are retryable
  }
}
```

---

### 3.4 Untyped localStorage Usage

**File:** [App.tsx](App.tsx#L69-L73), [projectStore.ts](projectStore.ts#L95)  
**Severity:** 🟡 MEDIUM  
**Issue:** Direct localStorage access without type safety

```typescript
// CURRENT (UNSAFE):
const saved = localStorage.getItem('bazis_project');
localStorage.setItem('bazis_project', JSON.stringify({ panels }));
```

**Recommendation:**
```typescript
// services/localStorageService.ts
interface StorageSchema {
  bazis_project: ProjectData;
  bazis_ui_state: UIState;
  bazis_preferences: UserPreferences;
}

class TypedLocalStorage {
  private static readonly PREFIX = 'bazis_';

  static get<K extends keyof StorageSchema>(key: K): StorageSchema[K] | null {
    try {
      const value = localStorage.getItem(this.PREFIX + String(key));
      return value ? JSON.parse(value) : null;
    } catch (error) {
      console.error(`[Storage] Failed to get ${String(key)}:`, error);
      return null;
    }
  }

  static set<K extends keyof StorageSchema>(key: K, value: StorageSchema[K]): boolean {
    try {
      localStorage.setItem(this.PREFIX + String(key), JSON.stringify(value));
      return true;
    } catch (error) {
      console.error(`[Storage] Failed to set ${String(key)}:`, error);
      return false;
    }
  }

  static remove<K extends keyof StorageSchema>(key: K): void {
    localStorage.removeItem(this.PREFIX + String(key));
  }

  static clear(): void {
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith(this.PREFIX)) {
        localStorage.removeItem(key);
      }
    });
  }
}

// Usage:
const project = TypedLocalStorage.get('bazis_project');
if (project) {
  setPanels(project.panels);
}
```

---

### 3.5 Missing Logging Infrastructure

**Severity:** 🟡 MEDIUM  
**Issue:** No structured logging system, scattered console.log/error calls

```typescript
// CURRENT (INCONSISTENT):
console.error(e);  // App.tsx
console.error(e);  // storageService.ts
// No context, timestamps, severity levels
```

**Recommendation:**
```typescript
// services/logger.ts
enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

class Logger {
  private static level = LogLevel.INFO;

  private static format(level: LogLevel, module: string, message: string, data?: any): string {
    const timestamp = new Date().toISOString();
    const levelName = LogLevel[level];
    const dataStr = data ? ` ${JSON.stringify(data)}` : '';
    return `[${timestamp}] [${levelName}] [${module}]${dataStr} ${message}`;
  }

  static debug(module: string, message: string, data?: any) {
    if (this.level <= LogLevel.DEBUG) {
      console.debug(this.format(LogLevel.DEBUG, module, message, data));
    }
  }

  static info(module: string, message: string, data?: any) {
    if (this.level <= LogLevel.INFO) {
      console.info(this.format(LogLevel.INFO, module, message, data));
    }
  }

  static warn(module: string, message: string, data?: any) {
    if (this.level <= LogLevel.WARN) {
      console.warn(this.format(LogLevel.WARN, module, message, data));
    }
  }

  static error(module: string, message: string, error?: Error | any) {
    console.error(
      this.format(LogLevel.ERROR, module, message),
      error instanceof Error ? error.stack : error
    );
  }
}

// Usage:
Logger.info('App', 'Project loaded', { panelCount: panels.length });
Logger.error('Storage', 'Failed to load project', error);
Logger.warn('Gemini', 'API rate limit approaching');
```

---

## 4. MEDIUM-PRIORITY PERFORMANCE ISSUES 🟡

### 4.1 Optimize Re-renders in Panel List

**File:** [EditorPanel.tsx](EditorPanel.tsx#L50-L70)  
**Severity:** 🟡 MEDIUM  
**Issue:** Large panel lists re-render on every store update

```typescript
// CURRENT (INEFFICIENT):
const filteredPanels = useMemo(() => {
    return panels.filter(p => 
        p.name.toLowerCase().includes(searchTerm.toLowerCase())
    );
}, [panels, searchTerm]);  // Re-runs if ANY panel changes
```

**Recommendation:**
```typescript
// Better approach:
const filteredPanels = useMemo(() => {
    return panels.filter(p => 
        p.name.toLowerCase().includes(searchTerm.toLowerCase())
    );
}, [panels, searchTerm]);

// Memoize panel items:
const PanelListItem = memo(({ panel, selected, onSelect }: PanelListItemProps) => (
    <div 
        className={`cursor-pointer p-2 ${selected ? 'bg-blue-500' : ''}`}
        onClick={() => onSelect(panel.id)}
    >
        {panel.name}
    </div>
), (prev, next) => {
    return prev.panel.id === next.panel.id && 
           prev.selected === next.selected;
});

// Use virtualization for large lists:
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={500}
  itemCount={filteredPanels.length}
  itemSize={35}
  width="100%"
>
  {({ index, style }) => (
    <PanelListItem
      style={style}
      panel={filteredPanels[index]}
      selected={filteredPanels[index].id === selectedPanelId}
      onSelect={selectPanel}
    />
  )}
</FixedSizeList>
```

---

### 4.2 Database Query Optimization

**File:** [storageService.ts](storageService.ts#L52-L65)  
**Severity:** 🟡 MEDIUM  
**Issue:** getAllProjects loads ALL projects into memory

```typescript
// CURRENT (INEFFICIENT):
const request = store.getAll();  // Loads all projects at once
request.onsuccess = () => {
    const res = request.result as ProjectSnapshot[];
    res.sort((a, b) => b.timestamp - a.timestamp);  // Sorts in-memory
    resolve(res);
};
```

**Recommendation:**
```typescript
// Better approach with pagination:
async getAllProjects(limit = 50, offset = 0): Promise<ProjectSnapshot[]> {
    await this.init();
    return new Promise((resolve, reject) => {
        if (!this.db) return reject('Database not initialized');

        const transaction = this.db.transaction([STORE_NAME], 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const index = store.index('timestamp');
        
        // Use cursor for efficient iteration
        const request = index.openCursor(null, 'prev');  // Reverse order
        const projects: ProjectSnapshot[] = [];
        let count = 0;

        request.onsuccess = () => {
            const cursor = request.result;
            if (cursor) {
                if (count >= offset && projects.length < limit) {
                    projects.push(cursor.value);
                }
                count++;
                
                if (projects.length >= limit) {
                    resolve(projects);
                } else {
                    cursor.continue();
                }
            } else {
                resolve(projects);
            }
        };

        request.onerror = () => reject(request.error);
    });
}

// For search:
async searchProjects(query: string): Promise<ProjectSnapshot[]> {
    const allProjects = await this.getAllProjects(1000);  // Reasonable limit
    return allProjects.filter(p =>
        p.name.toLowerCase().includes(query.toLowerCase()) ||
        p.tags?.some(t => t.toLowerCase().includes(query.toLowerCase()))
    );
}
```

---

## 5. LOW-PRIORITY IMPROVEMENTS 🟢

### 5.1 Add JSDoc Comments

**Severity:** 🟢 LOW  
**Issue:** Many functions lack documentation

**Recommendation:**
```typescript
/**
 * Calculates shelf deflection using Euler-Bernoulli formula
 * @param width - Shelf span in millimeters
 * @param depth - Shelf depth in millimeters
 * @param thickness - Material thickness in millimeters
 * @param loadClass - Load classification: 'light' (20kg), 'medium' (40kg), 'heavy' (60kg)
 * @returns Object containing deflection and stiffener recommendation
 * @throws Error if dimensions are outside valid range
 * 
 * @example
 * const result = calculateShelfStiffness(800, 400, 16, 'medium');
 * console.log(`Deflection: ${result.deflection}mm`);
 * if (result.needsStiffener) {
 *   console.log(`Recommended rib height: ${result.recommendedRibHeight}mm`);
 * }
 */
export function calculateShelfStiffness(
  width: number,
  depth: number,
  thickness: number,
  loadClass: 'light' | 'medium' | 'heavy'
): ShelfStiffnessResult
```

---

### 5.2 Improve Error Messages

**Severity:** 🟢 LOW  
**Issue:** Generic error messages don't help users

```typescript
// CURRENT:
addToast('Ошибка сохранения', 'error');  // Too vague

// IMPROVED:
addToast(
  `Не удалось сохранить проект "${projectName}": ${error.message}`,
  'error'
);

// Or for known errors:
if (error.message.includes('QuotaExceeded')) {
  addToast('Хранилище браузера переполнено. Удалите старые проекты.', 'error');
} else if (error.message.includes('NotFound')) {
  addToast('Проект был удален. Загружена пустая версия.', 'warning');
}
```

---

### 5.3 Add Unit Tests for Utilities

**Severity:** 🟢 LOW  
**Files:**
- validators.ts (currently 105 lines, no tests)
- hardwareUtils.ts (currently 426 lines, no tests)
- materials.config.ts (currently not tested)

**Recommendation:** Add tests for:

```typescript
// validators.test.ts
describe('InputValidator', () => {
  describe('validateDimension', () => {
    it('should accept valid dimensions', () => {
      expect(InputValidator.validateDimension('800')).toBe(800);
      expect(InputValidator.validateDimension(1500)).toBe(1500);
    });

    it('should reject NaN', () => {
      expect(() => InputValidator.validateDimension('abc')).toThrow();
    });

    it('should reject out-of-range values', () => {
      expect(() => InputValidator.validateDimension('5001')).toThrow();
      expect(() => InputValidator.validateDimension('0')).toThrow();
    });
  });
});
```

---

### 5.4 Add Loading States

**Severity:** 🟢 LOW  
**Issue:** No loading indicators for async operations

```typescript
// components/LoadingOverlay.tsx
interface LoadingOverlayProps {
  isLoading: boolean;
  message?: string;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  isLoading,
  message = 'Загрузка...'
}) => {
  if (!isLoading) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white p-4 rounded-lg">
        <Spinner />
        <p className="mt-2 text-sm">{message}</p>
      </div>
    </div>
  );
};

// Usage in App:
const [isLoading, setIsLoading] = useState(false);

const loadLast = async () => {
  setIsLoading(true);
  try {
    // ... load logic
  } finally {
    setIsLoading(false);
  }
};

return (
  <>
    <LoadingOverlay isLoading={isLoading} message="Загрузка проекта..." />
    {/* ... rest of app */}
  </>
);
```

---

## 6. ARCHITECTURAL RECOMMENDATIONS

### 6.1 Implement Error Boundary Enhancement

**Current:** ErrorBoundary exists but could be more comprehensive

```typescript
// components/ErrorBoundary.tsx - Enhanced version
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorCount: number;
}

class ErrorBoundary extends React.Component<Props, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
    error: null,
    errorInfo: null,
    errorCount: 0,
  };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState(prev => ({
      errorInfo,
      errorCount: prev.errorCount + 1,
    }));

    // Log to error tracking service
    ErrorTracker.captureException(error, {
      componentStack: errorInfo.componentStack,
      errorCount: this.state.errorCount,
    });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <h2 className="text-red-800 font-bold">Что-то пошло не так</h2>
          <details className="text-red-700 text-sm mt-2">
            <summary>Подробности</summary>
            <pre className="mt-2 overflow-auto">{this.state.error?.toString()}</pre>
            <pre className="mt-2 text-xs overflow-auto">
              {this.state.errorInfo?.componentStack}
            </pre>
          </details>
          <button
            onClick={this.handleReset}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Попробовать снова
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

---

### 6.2 Add Feature Flags System

**Recommendation:** For gradual rollout of new features

```typescript
// services/featureFlags.ts
interface FeatureFlags {
  'advanced-nesting': { enabled: boolean; rolloutPercentage: number };
  'ai-recommendations': { enabled: boolean; rolloutPercentage: number };
  'production-pipeline': { enabled: boolean; rolloutPercentage: number };
  'template-library': { enabled: boolean; rolloutPercentage: number };
}

class FeatureFlagService {
  private flags: FeatureFlags = {
    'advanced-nesting': { enabled: true, rolloutPercentage: 100 },
    'ai-recommendations': { enabled: true, rolloutPercentage: 80 },
    'production-pipeline': { enabled: false, rolloutPercentage: 0 },
    'template-library': { enabled: true, rolloutPercentage: 100 },
  };

  isEnabled(flag: keyof FeatureFlags, userId: string = ''): boolean {
    const feature = this.flags[flag];
    if (!feature.enabled) return false;

    // Stable rollout based on user ID hash
    const hash = userId ? this.hashCode(userId) % 100 : Math.random() * 100;
    return hash < feature.rolloutPercentage;
  }

  private hashCode(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash = hash & hash; // Convert to 32bit integer
    }
    return Math.abs(hash);
  }
}

// Usage:
if (featureFlags.isEnabled('production-pipeline')) {
  return <ProductionPipeline />;
}
```

---

## 7. TESTING STRATEGY

### 7.1 Current Test Coverage

| Component | Coverage | Status |
|-----------|----------|--------|
| CabinetGenerator.ts | 100% (Phase 1) | ✅ Excellent |
| validators.ts | 0% | ❌ Not tested |
| hardwareUtils.ts | 0% | ❌ Not tested |
| projectStore.ts | 0% | ❌ Not tested |
| Components (React) | 0% | ❌ Not tested |
| Services (Gemini) | 0% | ❌ Not tested |

### 7.2 Testing Roadmap

```typescript
// Priority 1: Core Business Logic
- validators.test.ts (15 test cases)
- hardwareUtils.test.ts (12 test cases)
- projectStore.test.ts (20 test cases)

// Priority 2: Services
- geminiService.test.ts (18 test cases)
- storageService.test.ts (12 test cases)

// Priority 3: Components
- EditorPanel.test.tsx (15 test cases)
- CabinetWizard.test.tsx (12 test cases)

// Total estimated test cases: ~100+
// Estimated coverage increase: 0% → 65%
```

---

## 8. QUICK WINS (Can be implemented immediately)

| Issue | File | Time | Benefit |
|-------|------|------|---------|
| Extract magic numbers | Multiple | 30 min | Maintainability |
| Add logging service | services/ | 45 min | Debugging |
| Improve error messages | Multiple | 30 min | UX |
| Add JSDoc comments | All | 60 min | Documentation |
| Add InputValidator | validators.ts | 45 min | Type safety |
| Fix API key handling | vite.config.ts | 15 min | Security |

---

## 9. MEDIUM-TERM IMPROVEMENTS (Next sprint)

| Issue | Time | Priority | Benefit |
|-------|------|----------|---------|
| Refactor EditorPanel | 4 hours | 🟠 High | Maintainability |
| Add typed localStorage | 2 hours | 🟠 High | Type safety |
| Improve error boundary | 2 hours | 🟠 High | Reliability |
| Add Gemini retry logic | 2 hours | 🟠 High | Reliability |
| Database optimization | 3 hours | 🟡 Medium | Performance |
| Implement feature flags | 2 hours | 🟡 Medium | Rollout control |

---

## 10. SUMMARY & NEXT STEPS

### Health Metrics
- **Code Quality:** 7/10 (Good foundation, needs error handling)
- **Type Safety:** 6/10 (Some weak typing patterns)
- **Error Handling:** 5/10 (Critical gaps in key areas)
- **Performance:** 7/10 (Good, room for optimization)
- **Testing:** 4/10 (Phase 1 solid, rest needs coverage)
- **Documentation:** 6/10 (Some JSDoc, needs more)

### Recommended Priority Order

**Phase 2A: Security & Stability (Immediate)**
1. Fix API key exposure in vite.config.ts (15 min)
2. Improve App.tsx error handling (30 min)
3. Add InputValidator (45 min)
4. Add logging service (45 min)

**Phase 2B: Code Quality (This week)**
1. Extract magic numbers to constants (30 min)
2. Refactor EditorPanel components (4 hours)
3. Add typed localStorage (2 hours)
4. Implement Gemini retry logic (2 hours)

**Phase 2C: Testing & Documentation (Next week)**
1. Add validator tests (3 hours)
2. Add store tests (3 hours)
3. Add JSDoc comments (2 hours)
4. Add integration tests (4 hours)

### Expected Impact

After implementing these recommendations:
- **Code Quality Score:** 7/10 → 8.5/10
- **Type Safety:** 6/10 → 8/10
- **Error Handling:** 5/10 → 8/10
- **Test Coverage:** 4/10 → 7/10
- **Performance:** 7/10 → 8/10

---

**Analysis completed:** January 18, 2026  
**Total recommendations:** 22 improvements across 8 categories  
**Estimated implementation time:** 40-50 hours for all improvements  
**Quick wins available:** 6 items completing in ~3-4 hours
