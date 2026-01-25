import { useState, useEffect } from 'react';
import { Panel, ProductionNorms } from '../types';
import { calculateNorms } from '../services/ProductionCalculator';

export const useProductionState = (panels: Panel[]) => {
  const [activeView, setActiveView] = useState<'pipeline' | 'dashboard'>('pipeline');
  const [norms, setNorms] = useState<ProductionNorms>({
    totalTimeMinutes: 0,
    cuttingTime: 0,
    edgingTime: 0,
    drillingTime: 0,
    assemblyTime: 0,
  });
  const [scannerInput, setScannerInput] = useState('');
  const [viewLabels, setViewLabels] = useState(false);

  useEffect(() => {
    setNorms(calculateNorms(panels));
  }, [panels]);

  return {
    activeView,
    setActiveView,
    norms,
    scannerInput,
    setScannerInput,
    viewLabels,
    setViewLabels,
  };
};
