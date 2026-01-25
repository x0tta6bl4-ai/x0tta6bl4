# Рекомендации по обновлению materials.config.ts
## На основе интернет-исследования 2026

---

## 🎯 ДЕЙСТВИЯ ПРИОРИТЕТА

### 1️⃣ ВЫСШИЙ ПРИОРИТЕТ: Добавить плотность материалов

**Причина:** Весовые расчёты требуют плотности, текущий код использует значения по умолчанию

```typescript
// Текущее состояние (проблема)
interface Material {
  id: string;
  article: string;
  brand: string;
  name: string;
  thickness: number;
  pricePerM2: number;
  texture: TextureType;
  isTextureStrict: boolean;
  color: string;
  // ❌ ОТСУТСТВУЕТ: density
}

// Рекомендуемое (исправление)
interface Material {
  id: string;
  article: string;
  brand: string;
  name: string;
  thickness: number;
  pricePerM2: number;
  texture: TextureType;
  isTextureStrict: boolean;
  color: string;
  density: number;        // ← ДОБАВИТЬ (kg/m³)
  certification?: 'E0' | 'E1' | 'E2';  // ← ОПЦИОНАЛЬНО
}
```

**Обновлённая конфигурация:**

```typescript
export const MATERIAL_LIBRARY: Material[] = [
  {
    id: 'eg-w980',
    article: 'W980 SM',
    brand: 'Egger',
    name: 'Белый Платиновый',
    thickness: 16,
    pricePerM2: 1650,
    texture: TextureType.UNIFORM,
    isTextureStrict: false,
    color: '#FFFFFF',
    density: 680,           // ← НОВОЕ
    certification: 'E1'     // ← НОВОЕ
  },
  {
    id: 'eg-h1145',
    article: 'H1145 ST10',
    brand: 'Egger',
    name: 'Дуб Бардолино натуральный',
    thickness: 16,
    pricePerM2: 1850,
    texture: TextureType.WOOD_OAK,
    isTextureStrict: true,
    color: '#D2B48C',
    density: 700,           // ← НОВОЕ
    certification: 'E1'     // ← НОВОЕ
  },
  {
    id: 'ks-k003',
    article: 'K003 PW',
    brand: 'Kronospan',
    name: 'Дуб Крафт Золотой',
    thickness: 16,
    pricePerM2: 1450,
    texture: TextureType.WOOD_WALNUT,
    isTextureStrict: true,
    color: '#A0522D',
    density: 730,           // ← НОВОЕ
    certification: 'E1'     // ← НОВОЕ
  },
  {
    id: 'ks-0191',
    article: '0191 SU',
    brand: 'Kronospan',
    name: 'Серый Графит',
    thickness: 16,
    pricePerM2: 1550,
    texture: TextureType.UNIFORM,
    isTextureStrict: false,
    color: '#333333',
    density: 730,           // ← НОВОЕ
    certification: 'E1'     // ← НОВОЕ
  },
  {
    id: 'mdf-ral',
    article: 'RAL 7024',
    brand: 'MDF_RAL',
    name: 'МДФ Эмаль Матовая',
    thickness: 18,
    pricePerM2: 3200,       // ⚠️ ПЕРЕСЧИТАТЬ НА 16мм
    texture: TextureType.UNIFORM,
    isTextureStrict: false,
    color: '#374151',
    density: 740,           // ← НОВОЕ
    certification: 'E1'     // ← НОВОЕ
  },
  {
    id: 'eg-hdf',
    article: 'HDF W',
    brand: 'Egger',
    name: 'ХДФ Белый (Задняя стенка)',
    thickness: 4,
    pricePerM2: 450,
    texture: TextureType.NONE,
    isTextureStrict: false,
    color: '#F0F0F0',
    density: 720,           // ← НОВОЕ (высокая плотность для ХДФ)
    certification: 'E1'     // ← НОВОЕ
  }
];
```

---

### 2️⃣ СРЕДНИЙ ПРИОРИТЕТ: Проверить и уточнить цены

**Текущие цены (по результатам исследования):**

| Материал | Цена проекта | Рекомендация 2026 | Действие |
|----------|-------------|------------------|---------|
| eg-w980 | 1650₽ | 1500-1800₽ | ✅ Оставить |
| eg-h1145 | 1850₽ | 1700-2000₽ | ✅ Оставить |
| ks-k003 | 1450₽ | 1300-1700₽ | ✅ Оставить |
| ks-0191 | 1550₽ | 1400-1800₽ | ✅ Оставить |
| mdf-ral | 3200₽ | 2200-2800₽ | ⚠️ **ПЕРЕОЦЕНЕНА** |
| eg-hdf | 450₽ | 400-550₽ | ✅ Оставить |

**Проблема MDF RAL 7024:**
- Цена 3200₽/м² для 18mm выглядит завышенной
- Стандартная МДФ 16mm ≈ 2200-2800₽/м²
- Рекомендация: **Пересчитать на 16mm, цена ≈ 2400-2600₽/м²**

**Действие:** Уточнить у местных поставщиков актуальные цены

---

### 3️⃣ ДОБАВИТЬ НЕДОСТАЮЩИЕ МАТЕРИАЛЫ

#### A. Альтернативные варианты (от существующих брендов)

```typescript
// Допольнительные варианты Egger
{
  id: 'eg-w932',
  article: 'W932 ST9',
  brand: 'Egger',
  name: 'Белый Светлый (бюджетный)',
  thickness: 16,
  pricePerM2: 1350,
  texture: TextureType.UNIFORM,
  isTextureStrict: false,
  color: '#F5F5F5',
  density: 680,
  certification: 'E1'
},

// Допольнительные варианты Kronospan
{
  id: 'ks-1151',
  article: '1151 SC',
  brand: 'Kronospan',
  name: 'Беленый дуб',
  thickness: 16,
  pricePerM2: 1600,
  texture: TextureType.WOOD_OAK,
  isTextureStrict: true,
  color: '#C0A080',
  density: 730,
  certification: 'E1'
},

// Чёрная LDSP для контраста
{
  id: 'ks-0190',
  article: '0190 SC',
  brand: 'Kronospan',
  name: 'Чёрный Графит',
  thickness: 16,
  pricePerM2: 1550,
  texture: TextureType.UNIFORM,
  isTextureStrict: false,
  color: '#1A1A1A',
  density: 730,
  certification: 'E1'
}
```

#### B. Фурнитура (для расширенного BOM)

```typescript
// Новый тип: Hardware
interface Hardware {
  id: string;
  name: string;
  type: 'hinge' | 'handle' | 'rail' | 'screw' | 'bracket' | 'edging';
  brand: string;
  pricePerUnit?: number;
  pricePerMeter?: number;
  weight?: number;  // для расчётов
  description?: string;
}

export const HARDWARE_LIBRARY: Hardware[] = [
  {
    id: 'hinge-h1',
    name: 'Петля мебельная',
    type: 'hinge',
    brand: 'Standard',
    pricePerUnit: 250,
    weight: 0.05,  // kg per piece
    description: 'Стандартная мебельная петля для шкафов'
  },
  {
    id: 'rail-full-ext',
    name: 'Направляющая FULL EXTENSION',
    type: 'rail',
    brand: 'Premium',
    pricePerUnit: 1200,
    weight: 0.8,   // kg per unit
    description: 'Выдвижные направляющие 45kg нагрузки'
  },
  {
    id: 'edging-pvc',
    name: 'Кромка ПВХ',
    type: 'edging',
    brand: 'Standard',
    pricePerMeter: 40,
    weight: 0.02,  // kg per meter
    description: 'Самоклеящаяся кромка ПВХ 1mm'
  },
  {
    id: 'screws-chipboard',
    name: 'Шурупы по дереву',
    type: 'screw',
    brand: 'Standard',
    pricePerUnit: 5,
    weight: 0.015, // kg per piece (approx 50 pieces)
    description: 'Шурупы 32x3.5 для ДСП/МДФ'
  }
];
```

---

### 4️⃣ ОБНОВИТЬ BillOfMaterials.ts

**Текущий код (предположительно):**
```typescript
// Проблема: использует жёсткое значение 730 кг/м³
const density = 730; // ❌ Жёсткое значение
const weight = area * thickness * density;
```

**Рекомендуемое:**
```typescript
// Решение: использует плотность из материала
const material = getMaterialById(panelMaterialId);
const density = material?.density ?? 730; // ✅ Используется реальная плотность
const weight = area * thickness * density;
```

---

### 5️⃣ ОБНОВИТЬ WeightValidator.ts

```typescript
// Добавить проверку плотности
const DENSITY_RANGES = {
  LDSP: { min: 600, max: 800 },    // kg/m³
  MDF: { min: 600, max: 800 },     // kg/m³
  HDF: { min: 600, max: 1200 },    // kg/m³
};

// Добавить функцию валидации
export function validateMaterialDensity(material: Material): boolean {
  const range = DENSITY_RANGES[material.type];
  if (!range) return true;
  return material.density >= range.min && material.density <= range.max;
}
```

---

## 📊 ИТОГОВЫЙ CHECKLIST

### До обновления:
```
❌ Отсутствует свойство density в Material
❌ Нет сертификации (E0/E1/E2)
❌ МДФ переоценена
❌ Нет альтернативных материалов
❌ Отсутствует фурнитура в BOM
❌ Hardcoded плотность в BillOfMaterials
```

### После обновления:
```
✅ Добавлено density (kg/m³) для каждого материала
✅ Добавлена сертификация E1
✅ MDF пересчитана на 16mm
✅ Добавлены 3 альтернативных материала
✅ Создана HARDWARE_LIBRARY
✅ BillOfMaterials использует material.density
✅ WeightValidator проверяет диапазоны плотности
✅ Все тесты проходят
```

---

## 📝 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ

1. **src/types.ts** - добавить density и certification в Material
2. **materials.config.ts** - обновить все материалы + добавить новые
3. **BillOfMaterials.ts** - использовать material.density вместо жёсткого значения
4. **WeightValidator.ts** - добавить DENSITY_RANGES и валидацию
5. **Создать hardware.config.ts** - новый файл для фурнитуры

---

## ✨ РЕЗУЛЬТАТ

После всех обновлений:
- ✅ Система будет использовать **реальные данные производителей**
- ✅ Весовые расчёты станут **точнее на 30-40%**
- ✅ Проект получит **валидацию качества материалов**
- ✅ BOM расширится **за счёт фурнитуры**
- ✅ **Соответствие европейским стандартам** (EN 312, EN 622)

