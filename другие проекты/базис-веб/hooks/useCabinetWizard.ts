import { useState } from 'react';
import { CabinetConfig, Section, CabinetItem } from '../types';

export const useCabinetWizard = (initialState?: { config: CabinetConfig; sections: Section[] }) => {
  const [config, setConfig] = useState<CabinetConfig>(
    initialState?.config || {
      name: 'Default Cabinet',
      type: 'straight',
      width: 1800,
      height: 2500,
      depth: 650,
      doorType: 'hinged',
      doorCount: 2,
      baseType: 'plinth',
      facadeStyle: 'solid'
    }
  );

  const [sections, setSections] = useState<Section[]>(
    initialState?.sections || [
      {
        id: '1',
        width: config.width,
        items: []
      }
    ]
  );

  const [selectedSectionId, setSelectedSectionId] = useState(0);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [showDoors, setShowDoors] = useState(true);

  const handleConfigChange = (newConfig: CabinetConfig) => {
    setConfig(newConfig);
  };

  const handleAddSection = () => {
    const newSection: Section = {
      id: `section-${Date.now()}`,
      width: 600,
      items: []
    };
    setSections([...sections, newSection]);
    setSelectedSectionId(sections.length);
  };

  const handleAddItem = (type: CabinetItem['type']) => {
    const newItem: CabinetItem = {
      id: `item-${Date.now()}`,
      type,
      name: type === 'shelf' ? 'Полка' : 
            type === 'drawer' ? 'Ящик' : 
            type === 'rod' ? 'Штанга' : 'Перегородка',
      y: config.baseType === 'legs' ? 100 : 70,
      height: type === 'drawer' ? 176 : 300
    };

    const newSections = [...sections];
    newSections[selectedSectionId].items.push(newItem);
    setSections(newSections);
    setSelectedItemId(newItem.id);
  };

  const handleSelectSection = (id: number) => {
    setSelectedSectionId(id);
    setSelectedItemId(null);
  };

  const handleSelectItem = (id: string | null) => {
    setSelectedItemId(id);
  };

  const handleMoveItem = (itemId: string, targetSecIdx: number, newY: number) => {
    const sourceSec = sections.findIndex(sec => 
      sec.items.some(item => item.id === itemId)
    );
    
    if (sourceSec === -1) return;

    const itemIndex = sections[sourceSec].items.findIndex(item => item.id === itemId);
    const [movedItem] = sections[sourceSec].items.splice(itemIndex, 1);
    
    const newSections = [...sections];
    newSections[targetSecIdx].items.push({
      ...movedItem,
      y: newY
    });
    
    newSections[targetSecIdx].items.sort((a, b) => a.y - b.y);
    setSections(newSections);
  };

  const handleResizeSection = (index: number, delta: number) => {
    const newSections = [...sections];
    const newWidth = Math.max(150, newSections[index].width + delta);
    
    // Adjust adjacent section
    if (index < newSections.length - 1) {
      newSections[index + 1].width = Math.max(150, newSections[index + 1].width - delta);
    }
    
    newSections[index].width = newWidth;
    setSections(newSections);
  };

  const handleUpdateItem = (itemId: string, updates: Partial<CabinetItem>) => {
    const newSections = sections.map(sec => ({
      ...sec,
      items: sec.items.map(item => 
        item.id === itemId ? { ...item, ...updates } : item
      )
    }));
    setSections(newSections);
  };

  const handleDeleteSelected = () => {
    if (selectedItemId) {
      const newSections = sections.map(sec => ({
        ...sec,
        items: sec.items.filter(item => item.id !== selectedItemId)
      }));
      setSections(newSections);
      setSelectedItemId(null);
    } else {
      if (sections.length > 1) {
        const newSections = sections.filter((_, index) => index !== selectedSectionId);
        setSections(newSections);
        setSelectedSectionId(Math.max(0, selectedSectionId - 1));
      }
    }
  };

  const handleDistributeItems = () => {
    const section = sections[selectedSectionId];
    if (section.items.length <= 1) return;

    const minY = config.baseType === 'legs' ? 100 : 70;
    const maxY = config.height - 16;
    const availableHeight = maxY - minY;
    const gap = 30;
    const itemHeight = availableHeight / section.items.length;

    const newSections = [...sections];
    newSections[selectedSectionId].items = section.items
      .map((item, index) => ({
        ...item,
        y: minY + index * (itemHeight + gap)
      }))
      .sort((a, b) => a.y - b.y);
    
    setSections(newSections);
  };

  return {
    config,
    sections,
    selectedSectionId,
    selectedItemId,
    showDoors,
    handleConfigChange,
    handleAddSection,
    handleAddItem,
    handleSelectSection,
    handleSelectItem,
    handleMoveItem,
    handleResizeSection,
    handleUpdateItem,
    handleDeleteSelected,
    handleDistributeItems
  };
};
