import { useMemo } from 'react';
import { AlertCircle, CheckCircle, AlertTriangle } from 'lucide-react';
import { CollisionValidator } from '../services/CollisionValidator';
import { HardwarePositionsValidator } from '../services/HardwarePositions';
import { Panel } from '../types';

interface ValidationPanelProps {
  panels: Panel[];
}

const ValidationPanel = ({ panels }: ValidationPanelProps) => {
  const validationResults = useMemo(() => {
    if (panels.length === 0) {
      return { errors: [], warnings: [] };
    }

    const errors: string[] = [];
    const warnings: string[] = [];

    try {
      // Collision Detection
      const collisions = CollisionValidator.validate(panels);
      collisions.forEach(c => {
        errors.push(`Пересечение: ${c.panelA} <-> ${c.panelB}`);
      });

      // Hardware Validation (System 32 standard)
      const hardwareResults = HardwarePositionsValidator.validatePositions(panels);
      hardwareResults.errors.forEach(e => errors.push(e));
      hardwareResults.warnings.forEach(w => warnings.push(w));
    } catch (e) {
      errors.push(`Ошибка валидации: ${String(e)}`);
    }

    return { errors, warnings };
  }, [panels]);

  const hasIssues = validationResults.errors.length > 0 || validationResults.warnings.length > 0;

  return (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-100">🔍 Результаты валидации</h3>
        {!hasIssues && <CheckCircle className="w-4 h-4 text-green-500" />}
      </div>

      {validationResults.errors.length > 0 && (
        <div className="mb-3">
          <div className="flex items-center gap-2 text-red-400 text-xs font-semibold mb-1">
            <AlertCircle className="w-3 h-3" />
            Ошибки ({validationResults.errors.length})
          </div>
          <ul className="text-xs text-red-300 space-y-1 pl-5">
            {validationResults.errors.map((err, i) => (
              <li key={i} className="list-disc">{err}</li>
            ))}
          </ul>
        </div>
      )}

      {validationResults.warnings.length > 0 && (
        <div>
          <div className="flex items-center gap-2 text-yellow-400 text-xs font-semibold mb-1">
            <AlertTriangle className="w-3 h-3" />
            Предупреждения ({validationResults.warnings.length})
          </div>
          <ul className="text-xs text-yellow-300 space-y-1 pl-5">
            {validationResults.warnings.map((warn, i) => (
              <li key={i} className="list-disc">{warn}</li>
            ))}
          </ul>
        </div>
      )}

      {!hasIssues && (
        <div className="text-xs text-green-400">
          ✓ Все проверки пройдены успешно
        </div>
      )}
    </div>
  );
};

export default ValidationPanel;
