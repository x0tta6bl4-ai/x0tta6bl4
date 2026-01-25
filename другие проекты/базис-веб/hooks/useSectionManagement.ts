import { useCallback, type Dispatch, type SetStateAction } from 'react';
import { Section, CabinetItem, CabinetConfig } from '../types';

interface UseSectionManagementProps {
  sections: Section[];
  setSections: Dispatch<SetStateAction<Section[]>>;
  config: CabinetConfig;
}

interface UseSectionManagementReturn {
  addItem: (type: CabinetItem['type'], sectionIndex: number) => void;
  deleteItem: (itemId: string) => void;
  updateItem: (itemId: string, updates: Partial<CabinetItem>) => void;
  addSection: () => void;
  removeSection: () => void;
  handleResizeSection: (index: number, delta: number) => void;
  distributeItems: (sectionIndex: number) => void;
}

export const useSectionManagement = ({
  sections,
  setSections,
  config,
}: UseSectionManagementProps): UseSectionManagementReturn => {
  const addItem = useCallback(
    (type: CabinetItem['type'], sectionIndex: number) => {
      const currentItems = [...sections[sectionIndex].items].sort((a, b) => a.y - b.y);
      const baseH = config.baseType === 'legs' ? 100 : config.doorType === 'sliding' ? 70 : 100;
      const topLimit = config.height - 32;
      const bottomLimit = baseH + 32;

      let bestY = (topLimit + bottomLimit) / 2;
      let maxGap = 0;

      let prevY = bottomLimit;
      const scanItems = [...currentItems, { y: topLimit, height: 0 }];

      for (const item of scanItems) {
        const isSpecial = 'type' in item && (item.type === 'partition' || item.type === 'drawer');
        const itemH = isSpecial ? (item.height || 16) : 16;
        const gap = item.y - prevY;
        if (gap > maxGap) {
          maxGap = gap;
          bestY = prevY + gap / 2;
        }
        prevY = item.y + itemH;
      }

      const h = type === 'drawer' ? 176 : type === 'partition' ? 300 : 16;

      if (maxGap < h + 10) {
        alert('Нет места для добавления элемента в эту секцию!');
        return;
      }

      bestY = Math.round(bestY / 32) * 32;

      const newItem: CabinetItem = {
        id: `item-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
        type,
        name:
          type === 'shelf'
            ? 'Полка'
            : type === 'drawer'
            ? 'Ящик'
            : type === 'rod'
            ? 'Штанга'
            : 'Перегородка',
        y: Math.round(bestY),
        height: h,
      };

      setSections(prev => {
        const next = [...prev];
        next[sectionIndex].items = [...next[sectionIndex].items, newItem];
        return next;
      });
    },
    [sections, setSections, config]
  );

  const deleteItem = useCallback(
    (itemId: string) => {
      setSections(prev => prev.map(s => ({ ...s, items: s.items.filter(i => i.id !== itemId) })));
    },
    [setSections]
  );

  const updateItem = useCallback(
    (itemId: string, updates: Partial<CabinetItem>) => {
      setSections(prev =>
        prev.map(s => ({
          ...s,
          items: s.items.map(i => (i.id === itemId ? { ...i, ...updates } : i)),
        }))
      );
    },
    [setSections]
  );

  const addSection = useCallback(() => {
    const newId = `section-${Date.now()}`;
    setSections(prev => [...prev, { id: newId, width: 0, items: [] }]);
  }, [setSections]);

  const removeSection = useCallback(() => {
    setSections(prev => {
      if (prev.length > 1) {
        return prev.filter((_, i) => i !== prev.length - 1);
      }
      return prev;
    });
  }, [setSections]);

  const handleResizeSection = useCallback(
    (index: number, delta: number) => {
      if (index < 0 || index >= sections.length - 1) return;
      setSections(prev => {
        const next = [...prev];
        const left = next[index];
        const right = next[index + 1];
        if (left.width + delta < 100 || right.width - delta < 100) return prev;
        next[index] = { ...left, width: Math.round(left.width + delta) };
        next[index + 1] = { ...right, width: Math.round(right.width - delta) };
        return next;
      });
    },
    [sections, setSections]
  );

  const distributeItems = useCallback(
    (sectionIndex: number) => {
      setSections(prev => {
        const next = [...prev];
        const section = next[sectionIndex];
        if (!section || section.items.length < 2) return prev;

        const items = [...section.items].sort((a, b) => a.y - b.y);

        const baseH = config.baseType === 'legs' ? 100 : config.doorType === 'sliding' ? 70 : 100;
        const roofOffset = config.construction === 'corpus' ? 16 : 0;

        const bottomLimit = baseH + 16;
        const topLimit = config.height - roofOffset;

        const totalVerticalSpace = topLimit - bottomLimit;
        const totalItemsHeight = items.reduce((acc, item) => acc + (item.height || 16), 0);

        const freeSpace = totalVerticalSpace - totalItemsHeight;
        if (freeSpace <= 0) return prev;

        const gap = freeSpace / (items.length + 1);

        let currentY = bottomLimit + gap;

        const newItems = items.map(item => {
          const h = item.height || 16;
          const newItem = { ...item, y: Math.round(currentY) };
          currentY += h + gap;
          return newItem;
        });

        next[sectionIndex] = { ...section, items: newItems };
        return next;
      });
    },
    [config, setSections]
  );

  return {
    addItem,
    deleteItem,
    updateItem,
    addSection,
    removeSection,
    handleResizeSection,
    distributeItems,
  };
};
