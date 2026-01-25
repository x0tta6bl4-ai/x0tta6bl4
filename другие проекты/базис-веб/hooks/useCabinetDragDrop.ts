import { useState, useEffect, useRef, RefObject } from 'react';
import { CabinetConfig, Section } from '../types';

interface DragState {
  id: string | number;
  startVal: number;
  startMouseY: number;
  startMouseX: number;
  type: 'item' | 'divider';
  offsetY: number;
}

interface UseCabinetDragDropProps {
  config: CabinetConfig;
  sections: Section[];
  wrapperRef: RefObject<HTMLDivElement>;
  scale: number;
  onMoveItem: (itemId: string, targetSecIdx: number, newY: number) => void;
  onResizeSection: (index: number, delta: number) => void;
}

interface UseCabinetDragDropReturn {
  dragState: DragState | null;
  snapLine: number | null;
  startDrag: (state: DragState) => void;
  calculateTargetSection: (relX: number) => number;
}

export const useCabinetDragDrop = ({
  config,
  sections,
  wrapperRef,
  scale,
  onMoveItem,
  onResizeSection,
}: UseCabinetDragDropProps): UseCabinetDragDropReturn => {
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [snapLine, setSnapLine] = useState<number | null>(null);

  const calculateTargetSection = (relX: number): number => {
    let currentX = 0;
    let targetSecIdx = -1;

    sections.forEach((s, i) => {
      if (relX >= currentX && relX < currentX + s.width) targetSecIdx = i;
      currentX += s.width + 16;
    });

    return targetSecIdx;
  };

  useEffect(() => {
    if (!dragState) return;

    const handleMove = (e: PointerEvent) => {
      if (!wrapperRef.current) return;

      if (dragState.type === 'item' && typeof dragState.id === 'string') {
        const rect = wrapperRef.current.getBoundingClientRect();
        const drawH = config.height * scale;
        const containerCenterY = rect.top + rect.height / 2;
        const cabinetBottomY = containerCenterY + drawH / 2;
        const relativeMouseY = cabinetBottomY - e.clientY;

        let newY = (relativeMouseY / scale) - dragState.offsetY;

        const baseH = config.baseType === 'legs' ? 100 : (config.doorType === 'sliding' ? 70 : 100);
        const minY = baseH + 16;
        const maxY = config.height - 16;

        newY = Math.max(minY, Math.min(newY, maxY));

        const contentWidth = config.width * scale;
        const startX = (rect.width - contentWidth) / 2;
        const relX = (e.clientX - rect.left - startX) / scale;

        const targetSecIdx = calculateTargetSection(relX);

        let activeSnapLine: number | null = null;

        if (!e.ctrlKey) {
          const SNAP_DIST = 20;
          let bestSnapY = -1;
          let minDiff = Infinity;

          sections.forEach((sec, idx) => {
            if (idx === targetSecIdx) return;

            sec.items.forEach(item => {
              const diff = Math.abs(item.y - newY);
              if (diff < SNAP_DIST && diff < minDiff) {
                minDiff = diff;
                bestSnapY = item.y;
              }
            });
          });

          if (bestSnapY === -1) {
            const gridY = Math.round(newY / 32) * 32;
            if (Math.abs(gridY - newY) < SNAP_DIST) {
              newY = gridY;
            }
          } else {
            newY = bestSnapY;
            activeSnapLine = bestSnapY;
          }
        }

        setSnapLine(activeSnapLine);

        if (targetSecIdx !== -1) {
          onMoveItem(dragState.id, targetSecIdx, newY);
        }
      } else if (dragState.type === 'divider' && typeof dragState.id === 'number') {
        const deltaX = (e.clientX - dragState.startMouseX) / scale;
        onResizeSection(dragState.id, deltaX);
        setDragState(prev => prev ? { ...prev, startMouseX: e.clientX } : null);
      }
    };

    const handleUp = () => {
      setDragState(null);
      setSnapLine(null);
    };

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
    return () => {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
    };
  }, [dragState, scale, config.height, config.baseType, config.doorType, sections, onMoveItem, onResizeSection, config.width]);

  return {
    dragState,
    snapLine,
    startDrag: setDragState,
    calculateTargetSection,
  };
};
