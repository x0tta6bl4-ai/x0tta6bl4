import { useState, useEffect } from 'react';
import { Panel } from '../types';

export const useEditorPanelState = (panels: Panel[], selectedPanelId: string | null) => {
  const [activeTab, setActiveTab] = useState<'structure' | 'properties'>('structure');
  const [editTab, setEditTab] = useState<'main' | 'edge' | 'drilling' | 'hardware'>('main');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    if (selectedPanelId) {
      setActiveTab('properties');
    } else {
      setActiveTab('structure');
    }
  }, [selectedPanelId]);

  return { activeTab, setActiveTab, editTab, setEditTab, searchTerm, setSearchTerm };
};
