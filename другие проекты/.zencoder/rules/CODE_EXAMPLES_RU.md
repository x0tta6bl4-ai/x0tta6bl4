# Примеры кода и диаграммы BazisLite-Web

## 1. Диаграмма архитектуры

```
┌─────────────────────────────────────────────────────────────────┐
│                        UI Components                             │
│ (Scene3D, EditorPanel, CutList, NestingView, ProductionPipeline)│
└────────┬───────────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────────────┐
│                      ProjectStore (Zustand)                      │
│  panels[], selectedPanel, history, CAD data, productionStage    │
└────────┬───────────────────────────────────────────────────────┘
         │
    ┌────┴────┐
    ↓         ↓
┌─────────────────────────────────┐  ┌──────────────────────────┐
│  InputValidator                 │  │  CabinetGenerator        │
│ • Validate dimensions           │  │ • generate(): Panel[]    │
│ • Check constraints             │  │ • generateWithConstraints│
│ • Type conversion               │  │ • calculateShelfStiffness│
│ • Error reporting               │  │ • generateHardware()     │
└─────────────────────────────────┘  └──────────────────────────┘
                                      │
                                      ↓
                         ┌────────────────────────────┐
                         │  ConstraintSolver          │
                         │ • solve() - Newton-Raphson│
                         │ • computeJacobian()        │
                         │ • solveLU()                │
                         │ • validateConstraints()    │
                         └────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ↓                 ↓                 ↓
        ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │ BillOfMaterials  │  │  DFMValidator    │  │ FEAIntegration   │
        │ • calcMass()     │  │ • validate()     │  │ • analyze()      │
        │ • calcCost()     │  │ • checkRules()   │  │ • stress()       │
        │ • calcTime()     │  │ • generateReport │  │ • deflection()   │
        │ • exportBOM()    │  │                  │  │                  │
        └──────────────────┘  └──────────────────┘  └──────────────────┘
                    │
                    ↓
        ┌──────────────────────────────┐
        │   geminiService              │
        │ • generateDesign()           │
        │ • auditConstruction()        │
        │ • askExpert()                │
        │ • optimizeDesign()           │
        └──────────────────────────────┘
                    │
                    ↓
        ┌──────────────────────────────┐
        │   hardwareUtils              │
        │ • validatePosition()         │
        │ • calculateOptimalPositions()│
        │ • generateHardwareArray()    │
        │ • checkInterferences()       │
        └──────────────────────────────┘
```

---

## 2. CabinetGenerator примеры кода

### 2.1 Базовая генерация

```typescript
import { CabinetGenerator, STD } from './services/CabinetGenerator';
import { MATERIAL_LIBRARY } from './materials.config';

const config: CabinetConfig = {
  name: 'Шкаф-купе',
  type: 'straight',
  width: 2400,      // мм
  height: 2200,     // мм
  depth: 650,       // мм
  doorType: 'sliding',
  doorCount: 2,
  baseType: 'legs',
  facadeStyle: 'combined'
};

const sections: Section[] = [
  { id: 1, width: 1200, items: [
    { id: '1-1', type: 'shelf', y: 800, height: 50, name: 'Полка' }
  ]},
  { id: 2, width: 1200, items: [
    { id: '2-1', type: 'rod', y: 1900, height: 0, name: 'Штанга' }
  ]}
];

const generator = new CabinetGenerator(config, sections, MATERIAL_LIBRARY);
const panels = generator.generate();

// Результат:
// panels[0]: боковая стенка левая (1200x2200x16)
// panels[1]: боковая стенка правая (1200x2200x16)
// panels[2]: крыша (2400x650x16)
// panels[3]: дно (2400x650x16)
// panels[4]: полка (1200x650x16)
// panels[5]: фасад двери левой (1200x2200x4)
// ...
```

### 2.2 Расчет прогиба полки

```typescript
// Полка 1200мм ширина, 650мм глубина, 16мм толщина, средняя нагрузка
const stiffness = generator.calculateShelfStiffness(
  width: 1200,
  depth: 650,
  thickness: 16,
  loadClass: 'medium'  // 40кг нагрузки
);

// Результат:
{
  deflection: 2.3,              // мм (прогиб)
  maxAllowed: 3.0,              // мм (норма)
  needsStiffener: false,        // Усилитель не нужен
  recommendedRibHeight: 0,      // мм
  supportSpacing: 32            // мм между опорами
}

// Если deflection > maxAllowed:
if (stiffness.needsStiffener) {
  // Добавить продольное усиление (rib) на нижнюю грань полки
  const rib: Panel = {
    id: 'rib-1',
    name: 'Усилитель полки',
    width: 1200,
    height: stiffness.recommendedRibHeight,
    depth: 50,
    x: 0, y: 800, z: 650 - 50,
    // ...
  };
  panels.push(rib);
}
```

### 2.3 Интеграция с ConstraintSolver

```typescript
// Генерация с ограничениями (ФАЗА 2)
const { panels, solverResult } = generator.generateWithConstraints();

if (!solverResult.success) {
  console.error('❌ Решатель не сошелся:', {
    iterations: solverResult.iterations,
    error: solverResult.error,
    message: solverResult.message
  });
} else {
  console.log('✅ Оптимизация завершена:', {
    iterations: solverResult.iterations,
    convergence: `${(solverResult.error * 1000).toFixed(2)}мм`
  });
  
  // Применить решение
  const optimizedPanels = panels.map(p => ({
    ...p,
    x: solverResult.positions.get(`panel_${p.id}`)?.x ?? p.x,
    y: solverResult.positions.get(`panel_${p.id}`)?.y ?? p.y,
    z: solverResult.positions.get(`panel_${p.id}`)?.z ?? p.z
  }));
}
```

---

## 3. ConstraintSolver примеры кода

### 3.1 Математическое ядро

```typescript
import { ConstraintSolver } from './services/ConstraintSolver';
import { Assembly, Component, Constraint, ConstraintType } from './types/CADTypes';

// Создать сборку с ограничениями
const assembly: Assembly = {
  id: 'cabinet-1',
  name: 'Шкаф-купе',
  components: [
    {
      id: 'body-left',
      name: 'Боковая стенка левая',
      type: 'body',
      position: { x: 0, y: 0, z: 0 },
      dimensions: { width: 650, height: 2200, depth: 16 },
      material: { id: 'eg-w980', name: 'Egger White Oak' }
    },
    {
      id: 'body-right',
      name: 'Боковая стенка правая',
      type: 'body',
      position: { x: 2400, y: 0, z: 0 },  // Изначально неверно
      dimensions: { width: 650, height: 2200, depth: 16 },
      material: { id: 'eg-w980', name: 'Egger White Oak' }
    },
    {
      id: 'shelf-1',
      name: 'Полка 1',
      type: 'shelf',
      position: { x: 0, y: 800, z: 0 },
      dimensions: { width: 2400, height: 16, depth: 650 },
      material: { id: 'eg-w980', name: 'Egger White Oak' }
    }
  ],
  constraints: [
    // Левая стенка зафиксирована
    {
      id: 'fix-left',
      type: ConstraintType.FIXED,
      component1Id: 'body-left',
      targetValue: { x: 0, y: 0, z: 0 }
    },
    // Правая стенка должна быть на расстоянии 2400мм от левой
    {
      id: 'dist-sides',
      type: ConstraintType.DISTANCE,
      component1Id: 'body-left',
      component2Id: 'body-right',
      targetValue: 2400
    },
    // Полка параллельна оси X
    {
      id: 'parallel-shelf',
      type: ConstraintType.PARALLEL,
      component1Id: 'shelf-1',
      component2Id: 'body-left'
    },
    // Полка на 800мм от дна
    {
      id: 'dist-shelf-bottom',
      type: ConstraintType.DISTANCE,
      component1Id: 'body-left',
      component2Id: 'shelf-1',
      targetValue: 800
    }
  ]
};

// Решить систему
const solver = new ConstraintSolver();
const initialPositions = new Map([
  ['body-left', { x: 0, y: 0, z: 0 }],
  ['body-right', { x: 2400, y: 0, z: 0 }],  // Может быть неверно
  ['shelf-1', { x: 0, y: 800, z: 0 }]
]);

const result = solver.solve(assembly, initialPositions, {
  tolerance: 0.001,      // 0.001мм точность
  maxIterations: 100,
  verbose: true
});

if (result.success && result.converged) {
  console.log(`✅ Сошелся за ${result.iterations} итераций`);
  console.log('Новые позиции:');
  for (const [componentId, pos] of result.positions) {
    console.log(`  ${componentId}: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)})`);
  }
} else {
  console.error('❌ Не сошелся:');
  for (const [constraintId, error] of result.constraintErrors) {
    console.log(`  Ошибка ${constraintId}: ${error.toFixed(4)}мм`);
  }
}
```

### 3.2 Newton-Raphson процесс

```typescript
// Визуализация итераций
interface IterationLog {
  iteration: number;
  residual: number;
  maxConstraintError: number;
  positions: Map<string, { x: number; y: number; z: number }>;
}

const iterationLogs: IterationLog[] = [];

// Модифицированный solve() с логированием
const result = solver.solve(assembly, initialPositions, { verbose: true });

// Вывод процесса сходимости:
// [Solver] Iteration 0: residual = 2.451238
// [Solver] Iteration 1: residual = 0.824510
// [Solver] Iteration 2: residual = 0.052341
// [Solver] Iteration 3: residual = 0.001223
// [Solver] Iteration 4: residual = 0.000001
// ✅ Сошелся за 5 итераций
```

---

## 4. geminiService примеры кода

### 4.1 Генерация конфигурации

```typescript
import { initializeGemini, generateDesignFromDescription } from './services/geminiService';

// Инициализировать Gemini с API ключом
await initializeGemini(process.env.VITE_GEMINI_API_KEY);

// Пользователь пишет на естественном языке
const userInput = `
  Мне нужен шкаф-купе для спальни.
  Ширина 2400мм, высота 2200мм, глубина 650мм.
  Две раздвижные двери.
  Внутри 3 отделения:
  - Первое отделение: вешалка для пальто
  - Второе отделение: 5 полок для одежды
  - Третье отделение: 2 ящика и полки
`;

try {
  const result = await generateDesignFromDescription(userInput);
  
  if (!result.success) {
    console.error('❌ Ошибка генерации:', result.error);
  } else {
    const { config, sections, optimization } = result.data;
    
    console.log(`✅ Конфигурация сгенерирована:`);
    console.log(`   Имя: ${config.name}`);
    console.log(`   Размеры: ${config.width}x${config.height}x${config.depth}`);
    console.log(`   Тип дверей: ${config.doorType}`);
    console.log(`   Отделения: ${sections.length}`);
    
    // Использовать конфигурацию
    const generator = new CabinetGenerator(config, sections, MATERIAL_LIBRARY);
    const panels = generator.generate();
  }
} catch (error) {
  if (error.code === 'QUOTA_EXCEEDED') {
    console.error('⏳ Превышен лимит запросов. Повторная попытка через 5 сек...');
    await new Promise(r => setTimeout(r, 5000));
  } else if (error.code === 'SAFETY_VIOLATION') {
    console.error('🚫 Запрос отклонен фильтрами безопасности');
  } else {
    console.error('❌ Неизвестная ошибка:', error.message);
  }
}
```

### 4.2 Аудит конструкции

```typescript
import { auditConstruction } from './services/geminiService';

const auditResult = await auditConstruction(panels, config);

// Результат имеет структуру:
{
  softCheck: {
    warnings: [
      {
        type: 'EFFICIENCY',
        message: 'Полка 1200мм на глубине 650мм будет провисать на 2.8мм при нагрузке 40кг',
        severity: 'WARNING',
        suggestion: 'Добавьте продольное усиление или поддерживающую направляющую'
      }
    ]
  },
  hardCheck: {
    errors: [
      {
        type: 'SAFETY',
        message: 'Четыре петли на двери 2200мм высотой — недостаточно (требуется 5)',
        severity: 'ERROR',
        suggestion: 'Добавьте 5-ю промежуточную петлю'
      }
    ]
  },
  optimization: {
    recommendations: [
      {
        area: 'cost',
        message: 'Можно использовать толщину 18мм вместо 22мм и сэкономить 12%',
        potential_saving: '8500₽'
      }
    ]
  }
}

// Вывести результаты
console.log('🔍 Аудит конструкции:');
if (auditResult.hardCheck.errors.length > 0) {
  console.log('❌ КРИТИЧЕСКИЕ ОШИБКИ:');
  auditResult.hardCheck.errors.forEach(e => {
    console.log(`   - ${e.message}`);
    console.log(`     💡 ${e.suggestion}`);
  });
}
if (auditResult.softCheck.warnings.length > 0) {
  console.log('⚠️ ПРЕДУПРЕЖДЕНИЯ:');
  auditResult.softCheck.warnings.forEach(w => {
    console.log(`   - ${w.message}`);
  });
}
```

### 4.3 Экспертные советы

```typescript
import { askExpert } from './services/geminiService';

const questions = [
  'Какая стандартная высота кухонного гарнитура?',
  'Как правильно рассчитать количество петель для двери?',
  'Какой максимальный пролет для полки из ДСП толщиной 16мм?'
];

for (const question of questions) {
  const answer = await askExpert(question);
  console.log(`❓ ${question}`);
  console.log(`✨ ${answer}\n`);
}

// Примерные ответы (на русском):
// ❓ Какая стандартная высота кухонного гарнитура?
// ✨ Стандартная высота кухонного гарнитура составляет 860-910 мм от пола до столешницы.
//    Это обеспечивает удобную рабочую высоту для большинства взрослых людей.
//    Высота подвесного шкафа над столешницей должна быть 400-500 мм.
```

---

## 5. BillOfMaterials примеры кода

### 5.1 Расчет сметы

```typescript
import { BillOfMaterials } from './services/BillOfMaterials';
import { MATERIAL_LIBRARY } from './materials.config';

const assembly: Assembly = {
  // ... сборка с компонентами
};

const materialPrices = {
  'eg-w980': 15000,      // ₽ за м³ (Egger White Oak)
  'kron-white': 12000,   // ₽ за м³ (Kronospan White)
  'mdf-ral7016': 18000   // ₽ за м³ (MDF RAL 7016)
};

const manufacturingOps = {
  machining: 500,        // ₽/час
  painting: 300,         // ₽/час
  assembly: 400,         // ₽/час
  qualityControl: 200,   // ₽/час
  packaging: 100         // ₽/изделие
};

const bom = new BillOfMaterials(assembly, materialPrices, manufacturingOps);

// Рассчитать смету
const bomData = bom.generate();
const bomStats = bom.getStats();

console.log('📊 Смета материалов:');
console.log(`   Всего компонентов: ${bomStats.totalItems}`);
console.log(`   Уникальных типов: ${bomStats.uniqueComponents}`);
console.log(`   Общая масса: ${bomStats.totalMass.toFixed(1)}кг`);
console.log(`   Стоимость материалов: ${bomStats.materialCost.toFixed(0)}₽`);
console.log(`   Стоимость производства: ${bomStats.manufacturingCost.toFixed(0)}₽`);
console.log(`   ИТОГО: ${bomStats.totalCost.toFixed(0)}₽`);
console.log(`   Время производства: ${bomStats.totalProductionTime.toFixed(1)}часов`);

// Экспорт в различные форматы
const csvExport = bom.exportCSV();
const jsonExport = bom.exportJSON();
const excelBuffer = bom.exportExcel();
```

---

## 6. DFMValidator примеры кода

### 6.1 Проверка производимости

```typescript
import { DFMValidator } from './services/DFMValidator';

const dfmConfig = {
  minWallThickness: 1.5,        // мм
  minFilletRadius: 0.5,         // мм
  maxAspectRatio: 10,           // высота/ширина
  minDistanceFromEdge: 3,       // мм
  maxHoleDensity: 2,            // на см²
  minDistanceBetweenHoles: 5,   // мм
  maxComponentWeight: 50,       // кг
  complexityThreshold: 20       // constraints
};

const dfmValidator = new DFMValidator(dfmConfig);

// Валидировать сборку
const dfmReport = dfmValidator.validateAssembly(assembly);

console.log('🏭 Проверка производимости:');

if (dfmReport.overallStatus === 'CRITICAL') {
  console.log('❌ КРИТИЧЕСКИЕ ПРОБЛЕМЫ:');
  dfmReport.checks
    .filter(c => c.severity === 'CRITICAL')
    .forEach(c => {
      console.log(`   ❌ ${c.message}`);
      console.log(`      Компонент: ${c.componentId}`);
      if (c.suggestedFix) {
        console.log(`      💡 Решение: ${c.suggestedFix}`);
      }
    });
}

if (dfmReport.checks.some(c => c.severity === 'ERROR')) {
  console.log('⚠️ ОШИБКИ:');
  dfmReport.checks
    .filter(c => c.severity === 'ERROR')
    .forEach(c => {
      console.log(`   ${c.message}`);
    });
}

// Расчет DFM Score (0-100)
const dfmScore = dfmValidator.calculateDFMScore(dfmReport);
console.log(`\n📈 DFM Score: ${dfmScore}/100 ${
  dfmScore >= 80 ? '✅ Хорошо' :
  dfmScore >= 60 ? '⚠️ Приемлемо' :
  '❌ Требует улучшений'
}`);
```

---

## 7. ProjectStore примеры кода

### 7.1 State Management

```typescript
import { useProjectStore } from './store/projectStore';

// Получить состояние
const {
  panels,
  selectedPanelId,
  history,
  solvedAssembly,
  bomData,
  dfmReport,
  currentGlobalStage,
  
  // Actions
  addPanel,
  updatePanel,
  bulkUpdatePanels,
  selectPanel,
  undo,
  redo,
  setSolvedAssembly,
  setBOMData,
  setDFMReport,
  setGlobalStage
} = useProjectStore();

// Добавить новую панель
const newPanel: Panel = {
  id: `panel-${Date.now()}`,
  name: 'Новая полка',
  width: 1200,
  height: 16,
  depth: 650,
  x: 0, y: 500, z: 0,
  materialId: 'eg-w980',
  color: '#FFFFFF',
  texture: TextureType.WOOD_OAK,
  textureRotation: 0,
  visible: true,
  layer: 'shelves',
  openingType: 'none',
  edging: { top: '2.0', bottom: '0.4', left: '0.4', right: '0.4' },
  groove: { enabled: false, side: 'top', width: 0, depth: 0, offset: 0 },
  hardware: []
};

addPanel(newPanel);

// Массовое обновление (с историей)
bulkUpdatePanels([
  {
    id: panel1.id,
    changes: { y: 800, visible: true }
  },
  {
    id: panel2.id,
    changes: { materialId: 'kron-white' }
  }
]);

// История (Undo/Redo)
undo();  // Отменить последнее изменение
redo();  // Вернуть отмененное

// Загрузить результаты CAD анализа
setSolvedAssembly(constraintSolverResult);
setBOMData(billOfMaterialsResult);
setDFMReport(dfmValidatorResult);

// Изменить этап производства
setGlobalStage('cutting');  // design -> cutting -> edging -> drilling -> ...
```

### 7.2 React Hook использование

```typescript
import React from 'react';
import { useProjectStore } from './store/projectStore';

const EditorComponent: React.FC = () => {
  const { 
    panels, 
    selectedPanelId, 
    updatePanel, 
    selectPanel,
    addToast
  } = useProjectStore();

  const selectedPanel = panels.find(p => p.id === selectedPanelId);

  const handleDimensionChange = (dimension: 'width' | 'height' | 'depth', value: number) => {
    if (selectedPanelId) {
      updatePanel(selectedPanelId, { [dimension]: value });
      addToast(`Размер изменен`, 'success');
    }
  };

  return (
    <div>
      <h2>Свойства панели</h2>
      {selectedPanel ? (
        <>
          <input
            type="number"
            value={selectedPanel.width}
            onChange={(e) => handleDimensionChange('width', Number(e.target.value))}
            placeholder="Ширина (мм)"
          />
          <input
            type="number"
            value={selectedPanel.height}
            onChange={(e) => handleDimensionChange('height', Number(e.target.value))}
            placeholder="Высота (мм)"
          />
          <input
            type="number"
            value={selectedPanel.depth}
            onChange={(e) => handleDimensionChange('depth', Number(e.target.value))}
            placeholder="Глубина (мм)"
          />
        </>
      ) : (
        <p>Выберите панель для редактирования</p>
      )}
    </div>
  );
};

export default EditorComponent;
```

---

## 8. Интеграционный workflow

### Полный цикл проектирования шкафа

```typescript
import { CabinetGenerator } from './services/CabinetGenerator';
import { ConstraintSolver } from './services/ConstraintSolver';
import { BillOfMaterials } from './services/BillOfMaterials';
import { DFMValidator } from './services/DFMValidator';
import { auditConstruction, generateDesignFromDescription } from './services/geminiService';
import { useProjectStore } from './store/projectStore';

// ЭТАП 1: Генерация конфигурации
async function designCabinet() {
  console.log('1️⃣ Генерация конфигурации...');
  const designResult = await generateDesignFromDescription(userInput);
  const { config, sections } = designResult.data;

  // ЭТАП 2: Создание 3D модели
  console.log('2️⃣ Создание 3D модели...');
  const generator = new CabinetGenerator(config, sections, MATERIAL_LIBRARY);
  const panels = generator.generate();
  
  // Сохранить в store
  const { setPanels } = useProjectStore.getState();
  setPanels(panels);

  // ЭТАП 3: Оптимизация позиций (ConstraintSolver)
  console.log('3️⃣ Оптимизация позиционирования...');
  const { panels: optimizedPanels, solverResult } = 
    generator.generateWithConstraints();
  
  if (solverResult.success) {
    setPanels(optimizedPanels);
  } else {
    throw new Error('Solver не сошелся');
  }

  // ЭТАП 4: Расчет сметы материалов
  console.log('4️⃣ Расчет сметы...');
  const assembly = generator.generateAssembly();
  const bom = new BillOfMaterials(assembly, MATERIAL_PRICES);
  const bomData = bom.generate();
  
  const { setBOMData } = useProjectStore.getState();
  setBOMData(bomData);

  // ЭТАП 5: Проверка производимости
  console.log('5️⃣ Проверка DFM...');
  const dfmValidator = new DFMValidator(DFM_CONFIG);
  const dfmReport = dfmValidator.validateAssembly(assembly);
  
  const { setDFMReport } = useProjectStore.getState();
  setDFMReport(dfmReport);

  // ЭТАП 6: AI аудит конструкции
  console.log('6️⃣ AI аудит...');
  const auditReport = await auditConstruction(optimizedPanels, config);
  
  if (auditReport.hardCheck.errors.length > 0) {
    console.warn('⚠️ Найдены критические ошибки. Требуется доработка.');
    return { success: false, errors: auditReport.hardCheck.errors };
  }

  // ✅ УСПЕШНО
  console.log('✅ Проектирование завершено!');
  return {
    success: true,
    panels: optimizedPanels,
    bom: bomData,
    dfm: dfmReport,
    audit: auditReport
  };
}

// Запустить
try {
  const result = await designCabinet();
  if (result.success) {
    console.log('📊 Финальный отчет:');
    console.log(`   Панелей: ${result.panels.length}`);
    console.log(`   Материалов: ${result.bom.totalItems}`);
    console.log(`   Стоимость: ${result.bom.totalCost}₽`);
    console.log(`   DFM Score: ${result.dfm.score}/100`);
  }
} catch (error) {
  console.error('❌ Ошибка при проектировании:', error.message);
}
```

---

## 9. Performance Tips

### 9.1 Оптимизация CabinetGenerator

```typescript
// ❌ ПЛОХО: Генератор пересоздается каждый раз
function generateDesign(config) {
  const gen = new CabinetGenerator(config, sections, materials);
  return gen.generate();
}

// ✅ ХОРОШО: Используйте кеширование
class DesignCache {
  private cache = new Map<string, Panel[]>();
  
  generate(config: CabinetConfig): Panel[] {
    const key = JSON.stringify(config);
    if (this.cache.has(key)) {
      return this.cache.get(key)!;
    }
    
    const gen = new CabinetGenerator(config, sections, materials);
    const result = gen.generate();
    this.cache.set(key, result);
    return result;
  }
}
```

### 9.2 Параллельные вычисления

```typescript
// Запустить BOM, DFM и FEA параллельно (не ждать друг друга)
async function analyzeAssembly(assembly: Assembly) {
  const [bomData, dfmReport, feaResults] = await Promise.all([
    billOfMaterials.calculate(assembly),
    dfmValidator.validate(assembly),
    feaIntegration.analyze(assembly)
  ]);
  
  return { bomData, dfmReport, feaResults };
}
```

### 9.3 Web Worker для тяжелых вычислений

```typescript
// Запустить Constraint Solver в отдельном потоке
const solverWorker = new Worker('constraint-solver.worker.ts');

solverWorker.postMessage({
  assembly: assembly,
  initialPositions: positions
});

solverWorker.onmessage = (event) => {
  const solverResult = event.data;
  console.log('Solver завершил:', solverResult);
};
```

---

## 10. Типичные ошибки и их исправления

### Ошибка 1: Забыли инвалидировать кеш

```typescript
// ❌ ОШИБКА
const gen = new CabinetGenerator(config1, ...);
gen.generate();  // Результаты для config1

// Где-то изменился config1
config1.width = 3000;

gen.generate();  // ❌ Вернет результаты для старого config, параметерный кеш не инвалидирован
```

**Решение**: добавить явную инвалидацию или использовать новый экземпляр генератора.

### Ошибка 2: Неверное преобразование единиц

```typescript
// ❌ ОШИБКА (смешивание метров и миллиметров)
const config = {
  width: 2.4,     // Хотел сказать 2.4м = 2400мм
  // Но система ожидает мм!
};

// ✅ ПРАВИЛЬНО
const config = {
  width: 2400,    // мм (явно указываем мм)
};
```

### Ошибка 3: Забыли обработать ошибки Gemini

```typescript
// ❌ ОШИБКА
const result = await generateDesign(input);  // Может упасть

// ✅ ПРАВИЛЬНО
try {
  const result = await generateDesign(input);
} catch (error) {
  if (error.code === 'QUOTA_EXCEEDED') {
    // Ждать и повторить
  } else if (error.code === 'SAFETY_VIOLATION') {
    // Изменить запрос
  } else {
    // Логировать и показать пользователю
  }
}
```

