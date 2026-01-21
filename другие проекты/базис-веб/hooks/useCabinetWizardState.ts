import { useState, useEffect } from 'react';
import { CabinetConfig, Section, CabinetItem } from '../types';

const DEFAULT_CONFIG: CabinetConfig = {
  name: 'Шкаф',
  type: 'straight',
  width: 1600,
  height: 2400,
  depth: 600,
  doorType: 'sliding',
  doorCount: 2,
  baseType: 'plinth',
  facadeStyle: 'combined',
  construction: 'corpus',
  backType: 'groove',
  hardwareType: 'confirmat',
  doorGap: 2,
  coupeGap: 26,
};

const DEFAULT_SECTIONS: Section[] = [
  {
    id: '1',
    width: 784,
    items: [
      { id: 'def-1', type: 'shelf', name: 'Полка', y: 480, height: 16 },
      { id: 'new-shelf-1', type: 'shelf', name: 'Новая Полка', y: 500, height: 16 },
      { id: 'def-2', type: 'shelf', name: 'Полка', y: 860, height: 16 },
      { id: 'def-3', type: 'shelf', name: 'Полка', y: 1240, height: 16 },
      { id: 'def-4', type: 'shelf', name: 'Полка', y: 1620, height: 16 },
      { id: 'def-5', type: 'shelf', name: 'Полка', y: 2000, height: 16 },
    ],
  },
  { id: '2', width: 784, items: [] },
];

interface UseCabinetWizardStateReturn {
  config: CabinetConfig;
  setConfig: (config: CabinetConfig) => void;
  sections: Section[];
  setSections: (sections: Section[]) => void;
  selectedSectionId: number;
  setSelectedSectionId: (id: number) => void;
  selectedItemId: string | null;
  setSelectedItemId: (id: string | null) => void;
  showDoors: boolean;
  setShowDoors: (show: boolean) => void;
  activeTab: 'global' | 'item';
  setActiveTab: (tab: 'global' | 'item') => void;
  errors: string[];
  setErrors: (errors: string[]) => void;
}

export const useCabinetWizardState = (
  initialState?: { config: CabinetConfig; sections: Section[] } | null
): UseCabinetWizardStateReturn => {
  const [config, setConfig] = useState<CabinetConfig>(initialState?.config || DEFAULT_CONFIG);
  const [sections, setSections] = useState<Section[]>(initialState?.sections || DEFAULT_SECTIONS);
  const [selectedSectionId, setSelectedSectionId] = useState(0);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [showDoors, setShowDoors] = useState(true);
  const [activeTab, setActiveTab] = useState<'global' | 'item'>('global');
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    if (selectedItemId) {
      setActiveTab('item');
    } else {
      setActiveTab('global');
    }
  }, [selectedItemId]);

  useEffect(() => {
    if (sections.length > 0) {
      const totalDividers = (sections.length - 1) * 16 + 32;
      const available = config.width - totalDividers;
      const w = Math.floor(available / sections.length);
      if (Math.abs(sections[0].width - w) > 5 && !initialState) {
        setSections(prev => prev.map(s => ({ ...s, width: w })));
      }
    }
  }, [config.width, sections.length, initialState]);

  return {
    config,
    setConfig,
    sections,
    setSections,
    selectedSectionId,
    setSelectedSectionId,
    selectedItemId,
    setSelectedItemId,
    showDoors,
    setShowDoors,
    activeTab,
    setActiveTab,
    errors,
    setErrors,
  };
};
