# ⚡ NEURAL CAD - QUICK REFERENCE

## 🎯 ОДНА СТРАНИЦА - ВСЁ ЧТО НУЖНО

### 1️⃣ УСТАНОВКА (5 мин)

```bash
cd базис-веб
pip install -r requirements-neural.txt
```

### 2️⃣ ОБУЧЕНИЕ (1-2 часа)

```bash
python scripts/train_neural_cad.py
# Результат: models/*.onnx + metadata.json ✅
```

### 3️⃣ РАЗВЁРТЫВАНИЕ (2 мин)

```bash
mkdir -p public/models
cp models/*.onnx public/models/
cp models/metadata.json public/models/
```

### 4️⃣ ИНТЕГРАЦИЯ (1 мин)

**Вариант A (быстро):**
```bash
mv App.tsx App.original.tsx
cp AppWithNeural.tsx App.tsx
```

**Вариант B (ручно):**
- Добавить `import NeuralGenerationPanel` в App.tsx
- Добавить `ViewMode.NEURAL` в enum
- Добавить кнопку в UI
- Добавить обработчик события (см. AppWithNeural.tsx)

### 5️⃣ ЗАПУСК (1 мин)

```bash
npm run dev
# http://localhost:3000
# Нажать Ctrl+N или кнопку "✨ Neural Gen"
```

---

## 📊 ПАРАМЕТРЫ (13 штук)

```typescript
{
  width: 1200,            // мм (300-3000)
  height: 1400,           // мм (400-2500)
  depth: 600,             // мм (300-1000)
  shelfCount: 3,          // кол-во (0-10)
  shelfThickness: 16,     // мм (4-25)
  edgeType: 1,            // 0=sharp, 1=rounded, 2=chamfered
  materialDensity: 800,   // kg/m³ (600-1200)
  hasDrawers: 0,          // 0 или 1
  drawerCount: 0,         // кол-во (0-4)
  doorType: 1,            // 0=none, 1=hinged, 2=sliding
  baseType: 0,            // 0=plinth, 1=legs
  customFeatures: 0,      // 0 или 1
  quality: 0.85           // 0.5-1.0
}
```

---

## 📈 РЕЗУЛЬТАТЫ

| Метрика | Значение |
|---------|----------|
| Vertices | ~5000 |
| Faces | ~8000 |
| Accuracy | 95%+ |
| Time | 1-3 сек (CPU), 100-300 мс (GPU) |
| Confidence | 0.85-0.99 |

---

## 🐛 ПРОБЛЕМЫ

| Проблема | Решение |
|----------|---------|
| "Failed to load models" | `ls public/models/` → должны быть .onnx файлы |
| "Out of memory" | F5 в браузере, или уменьшить batch_size |
| "Slow inference (>5s)" | Использовать GPU, или quality=0.7 |
| "Training doesn't start" | Проверить `python --version` (3.8+) и `pip install -r ...` |

---

## 🔗ССЫЛКИ НА ДОКУМЕНТЫ

| Нужно | Документ |
|------|----------|
| Быстрый старт | [NEURAL_QUICK_START.md](NEURAL_QUICK_START.md) |
| Контрольный список | [NEURAL_CHECKLIST.md](NEURAL_CHECKLIST.md) |
| Интеграция в App | [NEURAL_INTEGRATION_GUIDE.md](NEURAL_INTEGRATION_GUIDE.md) |
| Полная справка | [NEURAL_README.md](NEURAL_README.md) |
| Всё про обучение | [NEURAL_CAD_COMPLETE_GUIDE.md](NEURAL_CAD_COMPLETE_GUIDE.md) |
| Индекс документов | [NEURAL_DOCS_INDEX.md](NEURAL_DOCS_INDEX.md) |

---

## ✅ CHECKLIST

- [ ] Установить зависимости: `pip install -r requirements-neural.txt`
- [ ] Проверить GPU: `python -c "import torch; print(torch.cuda.is_available())"`
- [ ] Запустить обучение: `python scripts/train_neural_cad.py`
- [ ] Скопировать модели: `cp models/*.onnx public/models/`
- [ ] Интегрировать UI: Вариант A или B выше
- [ ] Запустить: `npm run dev`
- [ ] Протестировать: Ctrl+N → "✨ Сгенерировать 3D"

---

## 💡 СОВЕТЫ

**Быстрое обучение:**
```python
NUM_SAMPLES = 2000  # вместо 5000
EPOCHS = 30         # вместо 50
# Результат: 30 мин вместо 2 часов, 93-94% точность вместо 95%+
```

**Лучшая точность:**
```python
NUM_SAMPLES = 10000 # вместо 5000
EPOCHS = 100        # вместо 50
# Результат: 4 часа, 96%+ точность
```

**Быстрый инференс:**
```typescript
// Кэшировать результаты
const cache = new Map();
```

---

**Все команды на одной странице:** 👆
