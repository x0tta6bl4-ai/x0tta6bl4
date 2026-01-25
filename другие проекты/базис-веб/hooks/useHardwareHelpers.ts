import { useCallback } from 'react';
import { Hardware, Groove, Panel } from '../types';

interface UseHardwareHelpersProps {
  selectedPanel: Panel | undefined;
  updatePanel: (id: string, updates: Partial<Panel>) => void;
}

export const useHardwareHelpers = ({ selectedPanel, updatePanel }: UseHardwareHelpersProps) => {
  const addHardwarePreset = useCallback(
    (preset: 'hinge' | 'rail' | 'handle' | 'mounting') => {
      if (!selectedPanel) return;
      const hw: Hardware[] = [...(selectedPanel.hardware || [])];

      if (preset === 'hinge') {
        hw.push({
          id: `hw-${Date.now()}`,
          article: '71B3550',
          type: 'hinge_cup',
          name: 'Blum Clip Top (Чашка)',
          x: 37,
          y: 100,
          diameter: 35,
          depth: 13,
          price: 287,
        });
        hw.push({
          id: `hw-${Date.now()}-2`,
          article: '71B3550',
          type: 'hinge_cup',
          name: 'Blum Clip Top (Чашка)',
          x: 37,
          y: selectedPanel.height - 100,
          diameter: 35,
          depth: 13,
          price: 287,
        });
      } else if (preset === 'handle') {
        hw.push({
          id: `hw-${Date.now()}`,
          type: 'handle',
          name: 'Ручка-скоба 128мм',
          x: selectedPanel.width / 2,
          y: selectedPanel.height - 50,
          price: 150,
        });
      } else if (preset === 'rail') {
        hw.push({
          id: `hw-${Date.now()}`,
          article: 'QV6-450',
          type: 'slide_rail',
          name: 'Напр. Hettich 450мм',
          x: 37,
          y: 37,
          depth: 0,
          price: 680,
        });
      } else if (preset === 'mounting') {
        const margin = 50;
        const offset = 34;
        hw.push({
          id: `hw-${Date.now()}-1`,
          type: 'minifix_cam',
          name: 'Эксцентрик',
          x: margin,
          y: offset,
        });
        hw.push({
          id: `hw-${Date.now()}-2`,
          type: 'minifix_cam',
          name: 'Эксцентрик',
          x: selectedPanel.width - margin,
          y: offset,
        });
        hw.push({
          id: `hw-${Date.now()}-3`,
          type: 'minifix_cam',
          name: 'Эксцентрик',
          x: margin,
          y: selectedPanel.height - offset,
        });
        hw.push({
          id: `hw-${Date.now()}-4`,
          type: 'minifix_cam',
          name: 'Эксцентрик',
          x: selectedPanel.width - margin,
          y: selectedPanel.height - offset,
        });
      }

      updatePanel(selectedPanel.id, { hardware: hw });
    },
    [selectedPanel, updatePanel]
  );

  const updateGroove = useCallback(
    (changes: Partial<Groove>) => {
      if (!selectedPanel) return;
      const currentGroove = selectedPanel.groove || {
        enabled: false,
        side: 'top',
        width: 4,
        depth: 10,
        offset: 16,
      };
      updatePanel(selectedPanel.id, {
        groove: { ...currentGroove, ...changes },
      });
    },
    [selectedPanel, updatePanel]
  );

  return { addHardwarePreset, updateGroove };
};
