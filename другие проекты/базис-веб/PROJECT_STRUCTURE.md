# 📚 Структура проекта BASIS-WEB

## 📁 Корневые файлы

```
basis-web/
├── package.json              ← Зависимости и скрипты
├── tsconfig.json             ← Конфиг TypeScript
├── vite.config.ts            ← Конфиг Vite (сборка)
├── index.html                ← HTML точка входа
├── .env.local                ← Переменные окружения (API ключи)
├── .gitignore                ← Файлы игнорируемые git
│
├── START GUIDES (Начните отсюда!)
├── QUICK_START.md            ← ⚡ 30-секундный старт
├── SETUP_LOCAL.md            ← 📖 Полное руководство установки
├── README.md                 ← 📄 Описание проекта
│
├── IMPROVEMENTS & DOCS (Документация)
├── HARDWARE_IMPROVEMENTS.md  ← 🚀 Что было улучшено
├── HARDWARE_USER_GUIDE.md    ← 👥 Как использовать крепеж
├── HARDWARE_ANALYSIS.md      ← 🔍 Технический анализ
└── IMPROVEMENTS_REPORT.md    ← 📊 Финальный отчет
```

---

## 🗂️ Исходный код (src)

### Точки входа

```
index.tsx                    ← 🟢 ГЛАВНАЯ ТОЧКА ВХОДА
  ↓
index.html                   ← HTML контейнер для React
```

### Главный компонент

```
App.tsx                      ← 🟢 ГЛАВНЫЙ КОМПОНЕНТ
├── Управление состоянием (панели, слои, история)
├── Управление режимами просмотра
├── Интеграция всех компонентов
└── Обработка событий и синхронизация
```

### Типы данных

```
types.ts                     ← 🟢 ТИПЫ И ИНТЕРФЕЙСЫ
├── Axis (enum X, Y, Z)                    ← Ориентация панели
├── MaterialType (ЛДСП, МДФ, Стекло)      ← Материалы
├── TextureType (дерево, бетон)           ← Текстуры
├── Hardware (винт, эксцентрик, ручка)    ← Крепеж
├── Edging (кромка)                       ← Обработка краев
├── Groove (паз)                          ← Пазы
├── Layer (слой)                          ← Организация
└── Panel (деталь)                        ← ГЛАВНЫЙ ТИП - деталь мебели
```

---

## 🎨 Компоненты (components/)

### Основные компоненты

| Файл | Строк | Назначение |
|------|--------|-----------|
| **Scene3D.tsx** | 1360 | 🟡 3D визуализация (Three.js) - САМЫЙ БОЛЬШОЙ |
| **EditorPanel.tsx** | 908 | Редактор свойств и параметров |
| **App.tsx** | 424 | Главный компонент и логика |
| **DrawingView.tsx** | 91 | 2D чертежи и таблицы |
| **NestingView.tsx** | TBD | Оптимизация раскроя |
| **CutList.tsx** | TBD | Список материалов |
| **AIAssistant.tsx** | TBD | AI помощник |
| **ScriptEditor.tsx** | TBD | Программирование |
| **PanelDrawing.tsx** | TBD | Иконка панели |

### Структура компонента Scene3D (самый сложный)

```tsx
Scene3D.tsx (1360 строк)
├── Инициализация Three.js (100 строк)
│   ├── Создание сцены, камеры, освещения
│   ├── Создание рендерера
│   └── Инициализация контролов (орбит + трансформ)
│
├── Физическое моделирование (200 строк)
│   ├── Гравитация
│   ├── Стабилизация панелей через крепеж
│   └── Анимация открывания дверей
│
├── 3D Рендеринг (600 строк)
│   ├── Создание меша для каждой панели
│   ├── Кромки (edging)
│   ├── Пазы (groove)
│   ├── Крепеж (hardware)
│   ├── Текстуры
│   └── Подсвечивание выбранной панели
│
├── Интерактивность (300 строк)
│   ├── Раскастер (picking - выбор объектов)
│   ├── Трансформация (move, rotate, scale)
│   ├── Снэпинг к сетке
│   ├── Линии соединения
│   ├── Измерение расстояний
│   └── Контекстное меню
│
└── Визуальные режимы (160 строк)
    ├── Реалистичный (realistic)
    ├── Каркас (wireframe)
    └── Рентген (xray)
```

---

## ⚙️ Сервисы (services/)

### hardwareUtils.ts (НОВЫЙ - Улучшенный крепеж)

```typescript
hardwareUtils.ts (400 строк)
├── HardwareConfig          ← Конфигурация крепежа
├── validateHardwarePositions()  ← ✅ Валидация расстояний
├── selectOptimalHardwareType()  ← 🧠 Интеллектуальный выбор
├── calculateHardwareStats()     ← 📊 Статистика
├── getHardwareColor()           ← 🎨 Цвет в 3D
├── getHardwareDimensions()      ← 📐 Размеры
└── formatHardwareForExport()    ← 📄 Экспорт
```

**Использование:** Импортировать в EditorPanel.tsx для валидации и расчетов

### geminiService.ts

```typescript
geminiService.ts (175 строк)
├── generateFurnitureDesign()   ← 🤖 AI генерация дизайнов
├── optimizeCutList()            ← 📋 Оптимизация кроя
└── createClient()               ← 🔑 Инициализация API
```

**Требует:** VITE_GEMINI_API_KEY в .env.local

---

## 🔄 Поток данных

```
App.tsx (состояние)
    │
    ├─→ panels[]           (массив всех панелей)
    │   ├─→ Scene3D        (3D визуализация)
    │   ├─→ EditorPanel    (редактор)
    │   ├─→ DrawingView    (2D чертежи)
    │   └─→ CutList        (список кроя)
    │
    ├─→ layers[]           (организация)
    │   └─→ Scene3D        (видимость слоев)
    │
    ├─→ history            (Undo/Redo)
    │   └─→ EditorPanel    (кнопки undo/redo)
    │
    └─→ selectedPanelId    (выбранная панель)
        ├─→ Scene3D        (подсвечивание)
        └─→ EditorPanel    (показать свойства)
```

---

## 🎯 Основные типы данных

### Panel - ГЛАВНЫЙ ТИП

```typescript
Panel {
  id: string;                // Уникальный ID
  name: string;              // Имя (например, "Боковина левая")
  
  // Геометрия
  width: number;             // Ширина (мм)
  height: number;            // Высота (мм)
  depth: number;             // Глубина/толщина (мм)
  
  // Позиция в пространстве
  x, y, z: number;           // Координаты
  rotation: Axis;            // Ориентация (X, Y, Z)
  
  // Материал
  material: MaterialType;    // ЛДСП, МДФ, Стекло...
  color: string;             // HEX цвет (#C0C0C0)
  texture: TextureType;      // Дерево, бетон, нет
  textureRotation: 0|90;     // Направление текстуры
  
  // Видимость
  visible: boolean;          // Видна ли панель
  layer: string;             // ID слоя
  isSelected: boolean;       // Выбрана ли
  
  // Обработка
  edging: Edging;            // Кромка (0.4мм, 2мм)
  groove: Groove;            // Паз
  hardware: Hardware[];      // Крепеж (винты, ручки)
  
  // Другое
  openingType: 'none'|'left'|'right'|'top'|'bottom'|'drawer';
  isOpen: boolean;           // Дверь открыта?
}
```

### Hardware - Крепеж

```typescript
Hardware {
  id: string;                // Уникальный ID
  type: 'screw'|'minifix'|'dowel'|'handle'|'shelf_support'|'hinge';
  name: string;              // "Конфирмат 7x50"
  x: number;                 // Локальная координата X
  y: number;                 // Локальная координата Y
}
```

---

## 🚀 Как запустить

```bash
# 1. Установить зависимости
npm install

# 2. Запустить dev сервер
npm run dev

# 3. Открыть http://localhost:5173/ в браузере
```

---

## 📊 Размер файлов

| Компонент | Размер | Сложность |
|-----------|--------|----------|
| Scene3D.tsx | 1360 | 🔴🔴🔴 |
| EditorPanel.tsx | 908 | 🔴🔴 |
| App.tsx | 424 | 🟡🟡 |
| types.ts | ~100 | 🟢 |
| hardwareUtils.ts | 400 | 🟡 |
| geminiService.ts | 175 | 🟡 |
| **ВСЕГО** | **~3400** | **~20KB** |

---

## 🔍 Как найти нужный код

### Хочу изменить 3D визуализацию
→ `components/Scene3D.tsx` строки 1180-1210 (рендеринг крепежа)

### Хочу добавить новый тип крепежа
→ `services/hardwareUtils.ts` строки 19-60 (HARDWARE_CONFIG)
→ `types.ts` строка 26 (Hardware интерфейс)

### Хочу изменить валидацию крепежа
→ `services/hardwareUtils.ts` строки 80-120

### Хочу добавить новый режим просмотра
→ `components/Scene3D.tsx` строки 70-90 (visualStyle)

### Хочу использовать AI
→ `services/geminiService.ts` + `.env.local` (ключ API)

### Хочу добавить новую кнопку в редактор
→ `components/EditorPanel.tsx` строки 750-900

---

## 🎓 Рекомендуемый порядок изучения

1. **Начните здесь**
   - Прочитайте `types.ts` (понять структуру данных)
   - Посмотрите `App.tsx` (управление состоянием)

2. **Затем компоненты**
   - `EditorPanel.tsx` (проще всего)
   - `DrawingView.tsx` (простые таблицы)
   - `Scene3D.tsx` (сложнее всего)

3. **Потом сервисы**
   - `hardwareUtils.ts` (логика крепежа)
   - `geminiService.ts` (AI интеграция)

4. **И наконец optimization**
   - Профайлинг производительности
   - Оптимизация рендеринга

---

## 🔗 Зависимости (важные)

```json
{
  "dependencies": {
    "react": "^19.2.3",              // UI библиотека
    "react-dom": "^19.2.3",          // React для DOM
    "three": "^0.182.0",             // 3D графика
    "@google/genai": "^1.35.0",      // Google Gemini API
    "lucide-react": "^0.562.0",      // Иконки
    "recharts": "^3.6.0"             // Графики (для CutList)
  }
}
```

---

## 📞 Вопросы?

- 📖 Полная документация: `SETUP_LOCAL.md`
- 🚀 Улучшения: `HARDWARE_IMPROVEMENTS.md`
- 👥 Гайд по крепежу: `HARDWARE_USER_GUIDE.md`

---

**Версия:** 1.0 | **Дата:** 12 января 2026 | **Статус:** Production Ready ✅
