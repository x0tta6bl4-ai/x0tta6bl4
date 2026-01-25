import { ParametricSystem } from '../services/ParametricSystem';
import { Tolerance, CostBreakdown } from '../types/ParametricSystem';

/**
 * Пример использования параметрической системы v2.1
 * Демонстрирует основные функциональные возможности
 */

// Создаем экземпляр параметрической системы
const system = new ParametricSystem();

// ============================================
// 1. Управление параметрами
// ============================================
console.log('=== Управление параметрами ===');

// Получение параметра
const widthParam = system.getParameter('width');
if (widthParam) {
  console.log(`Текущий параметр "Ширина": ${widthParam.value} мм (${widthParam.min}-${widthParam.max})`);
}

// Изменение параметра
console.log('Изменяем ширину на 1300 мм...');
const updateResult = system.setParameter('width', 1300);
if (updateResult.validationErrors.length > 0) {
  console.error('Ошибки:', updateResult.validationErrors);
} else {
  const updatedParam = system.getParameter('width');
  console.log(`Обновлено: ${updatedParam?.value} мм`);
}

// Проверка параметров
console.log('\n=== Проверка параметров ===');
const validationErrors = system.validateParameters();
if (validationErrors.length > 0) {
  console.error('Некорректные параметры:', validationErrors);
} else {
  console.log('Все параметры корректны');
}

// ============================================
// 2. Управление допусками
// ============================================
console.log('\n=== Управление допусками ===');

// Добавление нового допуска
const newTolerance: Tolerance = {
  id: 'custom-tol-01',
  name: 'Геометрический допуск',
  type: 'dimensional',
  nominal: 0,
  upper: 0.3,
  lower: -0.3,
  unit: 'mm',
  description: 'Допуск для соединений'
};
system.addTolerance(newTolerance);
console.log(`Добавлен допуск: ${newTolerance.name}`);

// Запуск проверки
const toleranceReport = system.runToleranceCheck();
console.log(`Проверено: ${toleranceReport.totalChecks} параметров, OK: ${toleranceReport.passedChecks}`);

// ============================================
// 3. Расчет себестоимости
// ============================================
console.log('\n=== Расчет себестоимости ===');

// Проведение расчета
const costCalculation = system.calculateCost();
console.log(`Итоговая стоимость: ${costCalculation.totalCost} руб`);
console.log(`- Материалы: ${costCalculation.costBreakdown.materials.length} позиций`);
console.log(`- Фурнитура: ${costCalculation.costBreakdown.hardware.length} позиций`);
console.log(`- Работа: ${costCalculation.costBreakdown.labor.length} операции`);

// Экспорт отчета
const csvReport = system.exportCostReport('csv');
console.log('\nCSV отчет сформирован');

// ============================================
// 4. Генерация руководства сборки
// ============================================
console.log('\n=== Генерация руководства сборки ===');

const assemblyGuide = system.generateAssemblyGuide('ru');
console.log(`Руководство собрано: ${assemblyGuide.title}`);
console.log(`Всего шагов: ${assemblyGuide.steps.length}`);
console.log(`Основные инструменты: ${assemblyGuide.requiredTools.slice(0, 3).map(t => t.name).join(', ')}`);

// Экспорт в HTML
const htmlGuide = system.exportAssemblyGuide('html');
console.log('HTML руководство сформирован');

// ============================================
// 5. История версий
// ============================================
console.log('\n=== История версий ===');

// Создание новой версии
const v1 = system.saveVersion('Основная версия', 'Базовая конфигурация шкафа');
console.log(`Создал версию: ${v1.versionNumber} "${v1.name}"`);

// Изменяем параметр и сохраняем версию
system.setParameter('height', 2200);
const v2 = system.saveVersion('Высокий вариант', 'Увеличена высота на 200 мм');
console.log(`Создал версию: ${v2.versionNumber} "${v2.name}"`);

// Переключение между версиями
console.log('Переключаемся на версию v1.0.0...');
system.loadVersion(v1.id);
console.log(`Текущая версия: ${system.currentVersion}`);

// Возвращаемся
system.loadVersion(v2.id);
console.log(`Текущая версия: ${system.currentVersion}`);

// ============================================
// 6. Интерактивное редактирование
// ============================================
console.log('\n=== Интерактивное редактирование ===');

// Начало редактирования
system.startEditing();
system.toggleDraftMode();
console.log(`Режим редактирования: ${system.interactiveState.isEditing ? 'Вкл' : 'Выкл'}`);
console.log(`Режим черновика: ${system.interactiveState.draftMode.enabled ? 'Вкл' : 'Выкл'}`);

// Обновление параметров предпросмотра
system.updateRealTimePreview({
  cameraPosition: { x: 1000, y: 800, z: 1200 },
  lightingPreset: 'natural',
  wireframeMode: true
});
console.log('Параметры предпросмотра обновлены');

// Завершение редактирования
system.stopEditing(true);
console.log('Редактирование завершено');

// ============================================
// 7. Просмотр затрат по типам
// ============================================
console.log('\n=== Просмотр затрат ===');
const materialItems = system.getCostItemsByType('material');
const hardwareItems = system.getCostItemsByType('hardware');

console.log('Материалы:');
materialItems.forEach(item => {
  console.log(`- ${item.name}: ${item.quantity} м² × ${item.unitCost} руб/м² = ${item.totalCost} руб`);
});

console.log('Фурнитура:');
hardwareItems.forEach(item => {
  console.log(`- ${item.name}: ${item.quantity} шт × ${item.unitCost} руб/шт = ${item.totalCost} руб`);
});

console.log('\n✅ Пример использования параметрической системы завершен');