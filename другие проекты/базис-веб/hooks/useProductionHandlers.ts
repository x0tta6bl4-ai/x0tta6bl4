import { useCallback } from 'react';
import { Panel, ProductionStage, Material } from '../types';
import { generateCNCCSV, downloadCSV } from '../services/ProductionCalculator';

interface UseProductionHandlersProps {
  panels: Panel[];
  currentGlobalStage: ProductionStage;
  materialLibrary: Material[];
  setGlobalStage: (stage: ProductionStage) => void;
  setPanelStatus: (id: string, status: 'completed' | 'pending') => void;
  setScannerInput: (input: string) => void;
}

export const useProductionHandlers = ({
  panels,
  currentGlobalStage,
  materialLibrary,
  setGlobalStage,
  setPanelStatus,
  setScannerInput,
}: UseProductionHandlersProps) => {
  const handleStageComplete = useCallback(() => {
    const stages: ProductionStage[] = ['design', 'cutting', 'edging', 'drilling', 'assembly'];
    const idx = stages.indexOf(currentGlobalStage);
    if (idx < stages.length - 1) {
      setGlobalStage(stages[idx + 1]);
      panels.forEach((p) => setPanelStatus(p.id, 'pending'));
    } else {
      alert('Заказ полностью выполнен!');
    }
  }, [currentGlobalStage, setGlobalStage, panels, setPanelStatus]);

  const handleScan = useCallback(
    (e: any) => {
      e.preventDefault();
      const found = panels.find(
        (p) =>
          p.id.includes(e.currentTarget.scannerInput?.value || '') ||
          p.name.toLowerCase().includes((e.currentTarget.scannerInput?.value || '').toLowerCase())
      );
      if (found) {
        setPanelStatus(found.id, 'completed');
        setScannerInput('');
      } else {
        alert('Деталь не найдена');
      }
    },
    [panels, setPanelStatus, setScannerInput]
  );

  const generateCNC = useCallback(() => {
    const csv = generateCNCCSV(panels, materialLibrary);
    downloadCSV(csv, 'production_cnc.csv');
  }, [panels, materialLibrary]);

  return { handleStageComplete, handleScan, generateCNC };
};
