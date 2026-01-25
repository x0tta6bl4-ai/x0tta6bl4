import React, { useMemo } from 'react';
import { Panel } from '../types';
import { CollisionValidator } from '../services/CollisionValidator';
import { HardwarePositions } from '../services/HardwarePositions';
import { AlertCircle, CheckCircle, AlertTriangle } from 'lucide-react';

interface ValidationPanelProps {
  panels: Panel[];
}

/**
 * Компонент для отображения результатов валидации
 * Интегрирует CollisionValidator и HardwarePositions
 */
export const ValidationPanel: React.FC<ValidationPanelProps> = ({ panels }) => {
  // Выполняем валидацию
  const validation = useMemo(() => {
    const errors: { id: string; message: string; type: 'error' | 'warning' }[] = [];

    try {
      // 1. Проверяем коллизии
      const collisions = CollisionValidator.validate(panels);
      collisions.forEach(collision => {
        errors.push({
          id: `collision-${collision.panelA}-${collision.panelB}`,
          message: `⚠️ Пересечение: ${collision.panelA} ↔ ${collision.panelB} (расстояние: ${collision.distance.toFixed(1)}мм)`,
          type: 'error'
        });
      });

      // 2. Проверяем позиции фурнитуры (System 32)
      const hardwareErrors = HardwarePositions.validatePositions(panels);
      hardwareErrors.forEach(err => {
        errors.push({
          id: `hardware-${err.panelId}`,
          message: `🔧 ${err.message}`,
          type: err.severity === 'error' ? 'error' : 'warning'
        });
      });
    } catch (error) {
      console.error('Validation error:', error);
      errors.push({
        id: 'validation-error',
        message: `Ошибка при валидации: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`,
        type: 'error'
      });
    }

    // Разделяем на ошибки и предупреждения
    const errorList = errors.filter(e => e.type === 'error');
    const warningList = errors.filter(e => e.type === 'warning');

    return { errors: errorList, warnings: warningList, total: errors.length };
  }, [panels]);

  return (
    <div className="w-full space-y-3">
      {/* Summary */}
      <div className="flex gap-4 text-xs">
        <div className="flex items-center gap-1">
          {validation.errors.length === 0 ? (
            <CheckCircle className="w-4 h-4 text-green-500" />
          ) : (
            <AlertCircle className="w-4 h-4 text-red-500" />
          )}
          <span>Ошибок: <strong>{validation.errors.length}</strong></span>
        </div>
        <div className="flex items-center gap-1">
          <AlertTriangle className="w-4 h-4 text-yellow-500" />
          <span>Предупреждений: <strong>{validation.warnings.length}</strong></span>
        </div>
      </div>

      {/* Errors */}
      {validation.errors.length > 0 && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 space-y-2">
          <h3 className="text-xs font-bold text-red-400">❌ ОШИБКИ</h3>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {validation.errors.map(err => (
              <div key={err.id} className="text-xs text-red-300 flex gap-2">
                <span>•</span>
                <span>{err.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {validation.warnings.length > 0 && (
        <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-3 space-y-2">
          <h3 className="text-xs font-bold text-yellow-400">⚠️ ПРЕДУПРЕЖДЕНИЯ</h3>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {validation.warnings.map(warn => (
              <div key={warn.id} className="text-xs text-yellow-300 flex gap-2">
                <span>•</span>
                <span>{warn.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Success */}
      {validation.total === 0 && (
        <div className="bg-green-900/30 border border-green-700 rounded-lg p-3 text-center">
          <p className="text-xs text-green-300">✅ Все проверки пройдены успешно!</p>
        </div>
      )}

      {/* Stats */}
      <div className="text-xs text-slate-400 border-t border-slate-700 pt-2">
        <p>📊 Проверено панелей: {panels.length}</p>
        <p>🔍 Обнаружено проблем: {validation.total}</p>
      </div>
    </div>
  );
};

export default ValidationPanel;
