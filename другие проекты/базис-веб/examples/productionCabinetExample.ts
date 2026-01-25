import { ProductionCabinetBuilder } from '../services/ProductionCabinetBuilder';
import { CabinetDSL } from '../types/ProductionArchitecture';

/**
 * Пример создания производственного шкафа
 */

// Функция для создания Mm типа
const mm = (value: number) => value as any;

// Конфигурация шкафа в DSL формате
const cabinetDSL: CabinetDSL = {
  envelope: { 
    width: mm(1200), 
    height: mm(2000), 
    depth: mm(500) 
  },
  structure: { scheme: 'box' },
  material: {
    board: { 
      type: 'ldsp', 
      thickness: mm(16), 
      density: 650,
      pricePerM2: 1500
    },
    back: { 
      type: 'hdf', 
      thickness: mm(3), 
      density: 900,
      pricePerM2: 300
    },
    edge: {
      front: '2mm_abs',
      left: '1mm_pvc',
      right: '1mm_pvc',
      back: 'none',
      top: '1mm_pvc',
      bottom: '1mm_pvc'
    }
  },
  doors: { 
    count: 2, 
    type: 'swing', 
    gap: mm(3) 
  },
  shelves: { 
    count: 4, 
    supports: 'dowel_5x30',
    position: 'auto'
  },
  constraints: {
    maxDeflection: mm(12),
    minSafetyFactor: 1.5,
    manufacturingTolerance: mm(0.1),
    jointType: 'confirmat'
  }
};

// Создаём строитель
const builder = new ProductionCabinetBuilder();

// Запускаем сборку
const run = async () => {
  try {
    console.log('🚀 Начинаем сборку шкафа...');
    
    const model = await builder.build(cabinetDSL);
    
    console.log('✅ Модель собрана успешно!');
    console.log('📊 Статистика:');
    console.log(`   • Панелей: ${model.solved.size}`);
    console.log(`   • Соединений: ${model.joints.length}`);
    console.log(`   • Листов материала: ${model.cutting.metrics.totalSheets}`);
    console.log(`   • КИМ: ${model.cutting.metrics.KIM.toFixed(1)}%`);
    console.log(`   • Отходы: ${model.cutting.metrics.totalWaste.toFixed(2)} мм²`);
    console.log(`   • Время на резку: ${model.cutting.metrics.estimatedCuttingTime.toFixed(1)} мин`);
    
    if (model.validation.errors.length > 0) {
      console.log('❌ Ошибки:', model.validation.errors);
    }
    
    if (model.validation.warnings.length > 0) {
      console.log('⚠️ Предупреждения:', model.validation.warnings);
    }
    
    // Экспортируем в DXF
    const dxf = model.export.toDXF();
    console.log('\n📄 DXF экспорт успешно:');
    console.log(dxf.substring(0, 500) + '...');
    
    // Экспортируем в JSON
    const json = model.export.toJSON();
    console.log('\n📄 JSON экспорт успешно:');
    console.log(json.substring(0, 500) + '...');
    
  } catch (error) {
    console.error('❌ Ошибка сборки:', error);
  }
};

// Запускаем
run();
