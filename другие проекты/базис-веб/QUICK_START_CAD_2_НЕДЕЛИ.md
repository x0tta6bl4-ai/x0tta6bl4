# 🚀 Быстрый Старт: Внедрение CAD в Базис-Веб за 2 Недели

**День-за-днём план действий**

---

## 📅 Неделя 1: Основной Параметрический Двигатель

### День 1: Подготовка (2 часа)

```bash
# 1. Создать новые файлы
mkdir -p backend/services/cad
mkdir -p backend/routes
mkdir -p frontend/components/CAD

# 2. Установить зависимости (если нужны)
npm install uuid pdfkit dxf-writer
npm install --save-dev @types/uuid

# 3. Настроить VS Code для TypeScript
# Убедиться что tsconfig.json актуален
```

### День 2-3: CabinetGenerator.ts (12 часов)

**План:**
1. Скопировать из `CAD_ПРАКТИЧЕСКАЯ_РЕАЛИЗАЦИЯ.md` класс `CabinetModeler`
2. Перевести в TypeScript файл `/backend/services/cad/CabinetGenerator.ts`
3. Добавить тесты

```bash
# Проверка синтаксиса
npx tsc --noEmit

# Запуск тестов
npm test -- CabinetGenerator.test.ts
```

**Checklist:**
- ✅ Класс скопирован и типизирован
- ✅ Все методы работают без ошибок
- ✅ Базовые тесты пройдены

### День 4: API Endpoints (8 часов)

Скопировать маршруты из `CAD_ПРАКТИЧЕСКАЯ_РЕАЛИЗАЦИЯ.md`:

```typescript
// /backend/routes/cabinet.ts
// - POST /api/cabinet/generate
// - GET /api/cabinet/materials
// - POST /api/cabinet/export
```

**Тестирование:**
```bash
curl -X POST http://localhost:3000/api/cabinet/generate \
  -H "Content-Type: application/json" \
  -d '{
    "width": 800,
    "height": 2000,
    "depth": 350,
    "material": "plywood_18",
    "shelvesCount": 3
  }'
```

**Checklist:**
- ✅ Все endpoints работают
- ✅ Модель генерируется корректно
- ✅ Расчёты стоимости правильные

### День 5: Интеграция с Frontend (10 часов)

1. **Создать компонент AdvancedCabinetWizard.tsx** из кода
2. **Обновить App.tsx:**

```typescript
// App.tsx
import AdvancedCabinetWizard from './components/AdvancedCabinetWizard';

// Добавить роут
<Route path="/design/advanced" element={<AdvancedCabinetWizard />} />
```

3. **Добавить CSS:**

```css
/* styles/cabinet-wizard.css */
.cabinet-wizard-container {
  display: grid;
  grid-template-columns: 300px 1fr 350px;
  gap: 20px;
  height: calc(100vh - 100px);
}

.wizard-left, .wizard-right {
  overflow-y: auto;
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
}

.wizard-center {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.param-group {
  margin-bottom: 15px;
}

.cost-display {
  background: #e8f5e9;
  padding: 15px;
  border-radius: 6px;
  margin-top: 20px;
}

.cost-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #ddd;
}

.cost-row.total {
  font-size: 18px;
  font-weight: bold;
  border-bottom: none;
  color: #2e7d32;
}
```

**Checklist:**
- ✅ Компонент отображается
- ✅ Параметры изменяются в реальном времени
- ✅ 3D модель обновляется

---

## 📅 Неделя 2: Производственные Функции + Тестирование

### День 6: NestingOptimizer.ts (10 часов)

1. Скопировать класс `NestingOptimizer` из документации
2. Файл: `/backend/services/cad/NestingOptimizer.ts`
3. Добавить endpoint: `POST /api/cabinet/nesting`

```bash
# Тестирование
curl -X POST http://localhost:3000/api/cabinet/nesting \
  -H "Content-Type: application/json" \
  -d '{
    "cutList": [...],
    "sheetWidth": 2800,
    "sheetHeight": 1200
  }'
```

**Результат:**
```json
{
  "sheets": [...],
  "efficiency": 87.5,
  "waste": 312.5
}
```

### День 7-8: Экспорт и UI для Cut List (12 часов)

**PDF Экспорт:**
```typescript
// services/cad/ExportService.ts
import PDFDocument from 'pdfkit';

class ExportService {
  exportToPDF(model: CabinetModel): Buffer {
    const doc = new PDFDocument();
    
    // Заголовок
    doc.fontSize(20).text('Cabinet Assembly Drawing', 50, 50);
    
    // Параметры
    doc.fontSize(12).text(`Width: ${model.params.width}mm`, 50, 100);
    doc.text(`Height: ${model.params.height}mm`, 50, 120);
    
    // Cut List таблица
    this.drawCutListTable(doc, model.cutList);
    
    return doc;
  }
}
```

**Компонент CutListView:**
```typescript
export const CutListView: React.FC<{ cutList: CutListItem[] }> = ({ cutList }) => {
  return (
    <div className="cut-list">
      <h3>Cut List ({cutList.length} parts)</h3>
      <table>
        <thead>
          <tr>
            <th>Part</th>
            <th>Qty</th>
            <th>L×W×T (mm)</th>
            <th>Material</th>
            <th>Weight (kg)</th>
          </tr>
        </thead>
        <tbody>
          {cutList.map(item => (
            <tr key={item.id}>
              <td>{item.partName}</td>
              <td>{item.quantity}</td>
              <td>
                {item.dimensions.length}×{item.dimensions.width}×{item.dimensions.thickness}
              </td>
              <td>{item.material}</td>
              <td>{(item.weight * item.quantity).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      
      {/* Export Buttons */}
      <div className="export-buttons">
        <button onClick={() => exportPDF(cutList)}>📄 PDF</button>
        <button onClick={() => exportCSV(cutList)}>📊 CSV</button>
      </div>
    </div>
  );
};
```

### День 9: Интеграция с Ollama (8 часов)

Добавить AI анализ конструкции:

```typescript
// POST /api/cabinet/ai/analyze

const analyzeConstruction = async (model: CabinetModel) => {
  const { askFurnitureExpert } = await import('./ollamaService');
  
  const prompt = `
Проанализируй конструкцию шкафа:
- Размеры: ${model.params.width}×${model.params.height}×${model.params.depth}mm
- Материал: ${model.params.material}
- Полок: ${model.params.shelvesCount}
- Вес: ${model.properties.estimatedWeight}kg
- Грузоподъёмность: ${model.properties.loadCapacity.perShelf}kg/полка

Вопросы:
1. Достаточна ли стабильность? 
2. Нужны ли усиления?
3. Как оптимизировать стоимость?
4. Какие материалы лучше?
  `;
  
  return await askFurnitureExpert(prompt);
};
```

### День 10: Тестирование и Documentation (12 часов)

**Unit Tests (Jest):**
```typescript
// __tests__/CabinetGenerator.test.ts
import { CabinetModeler } from '../services/CabinetGenerator';

describe('CabinetModeler', () => {
  const modeler = new CabinetModeler();

  test('generates valid cabinet model', () => {
    const model = modeler.generateCabinet({
      width: 800,
      height: 2000,
      depth: 350,
      material: 'plywood_18',
      shelvesCount: 3
    });

    expect(model.id).toBeDefined();
    expect(model.cost.finalPrice).toBeGreaterThan(0);
    expect(model.cutList.length).toBeGreaterThan(0);
  });

  test('validates dimensions', () => {
    expect(() => {
      modeler.generateCabinet({
        width: 100,      // Слишком маленькая
        height: 2000,
        depth: 350,
        material: 'plywood_18',
        shelvesCount: 3
      });
    }).toThrow('Width must be between 300-2400mm');
  });

  test('calculates cost correctly', () => {
    const model = modeler.generateCabinet({
      width: 800,
      height: 2000,
      depth: 350,
      material: 'plywood_18',
      shelvesCount: 3
    });

    const cost = model.cost.finalPrice;
    expect(cost).toBeGreaterThan(model.cost.materials.total);
  });
});
```

**Integration Tests:**
```bash
# Тестировать API
npm run test:integration

# Запустить dev сервер
npm run dev

# Открыть http://localhost:3000/design/advanced
```

**Checklist:**
- ✅ Все unit тесты пройдены
- ✅ API работает корректно
- ✅ Frontend интегрирован
- ✅ Можно экспортировать PDF
- ✅ AI рекомендации работают

---

## 🎯 Финальный Чек-лист (Готово к Production)

### Backend ✅
- [ ] CabinetModeler class полностью функционален
- [ ] NestingOptimizer работает с эффективностью >85%
- [ ] Все API endpoints работают
- [ ] Экспорт в PDF/DXF/STEP работает
- [ ] Интеграция с Ollama работает
- [ ] База данных содержит материалы
- [ ] Error handling на месте
- [ ] Логирование включено

### Frontend ✅
- [ ] AdvancedCabinetWizard компонент готов
- [ ] Real-time обновление 3D модели
- [ ] Cut List отображается корректно
- [ ] Nesting диаграмма работает
- [ ] Export buttons функциональны
- [ ] Responsive design работает
- [ ] Нет console errors

### Testing ✅
- [ ] Unit tests: 100% покрытие критических методов
- [ ] Integration tests: все API endpoints тестированы
- [ ] E2E tests: основные сценарии пройдены
- [ ] Performance: модель генерируется <500ms
- [ ] Browser compatibility: Chrome/Firefox/Safari

### Documentation ✅
- [ ] README для разработчиков
- [ ] API документация (Swagger/OpenAPI)
- [ ] User guide для дизайнеров
- [ ] Code comments на критических местах

---

## 💻 Команды для Развёртывания

### Development
```bash
# Терминал 1: Backend
npm run dev:backend

# Терминал 2: Frontend
npm run dev:frontend

# Терминал 3: Database
npm run db:dev
```

### Testing
```bash
npm run test              # Все тесты
npm run test:unit        # Только unit
npm run test:integration # Только интеграция
npm run test:coverage    # Coverage report
```

### Production
```bash
npm run build
npm run build:backend
npm run start:prod
```

---

## 📊 Ожидаемые Результаты

| Метрика | Базовая | После CAD | Улучшение |
|---------|---------|-----------|-----------|
| Время дизайна шкафа | 30 мин | 5 мин | **6x быстрее** |
| Ошибки в размерах | ~5% | <0.1% | **50x точнее** |
| Расчёт стоимости | 10 мин | реал-тайм | Мгновенно |
| Экспорт чертежей | ручной | 1-клик | Автоматично |
| Стоимость производства | €100+ часов | €50 часов | **50% дешевле** |

---

## 🚀 Очередь на Месяц 2 (Опционально)

После успешного внедрения базовой версии:

1. **WebGL интеграция** - Полноценный 3D редактор (вместо preview)
2. **OnShape API** - Интеграция с профессиональным CAD для экспертов
3. **Параметрические сборки** - Сложные конструкции с множественными компонентами
4. **Система расценок** - Динамические цены по регионам
5. **Мобильное приложение** - React Native версия

---

**Документ готов к использованию!**

**Время реализации:** 2 недели (одного разработчика)  
**Сложность:** Средняя  
**ROI:** €2,000-3,000/год экономии

Начнём в понедельник! 🚀
