
import React, { createContext, useContext, ReactNode, useCallback, useEffect } from 'react';
import { CabinetParams, CabinetMaterialType } from '../types';
import { useHistory } from '../hooks/useHistory';
import { useProjectStore } from '../store/projectStore';

interface CabinetContextType {
  params: CabinetParams;
  updateParams: (changes: Partial<CabinetParams>) => void;
  addShelf: (y?: number) => void;
  addDrawer: (y: number) => void;
  removeItem: (id: string, type: 'shelf' | 'drawer') => void;
  setMaterial: (mat: CabinetMaterialType) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
}

const DEFAULT_PARAMS: CabinetParams = {
  name: 'Новый проект',
  width: 800,
  height: 2000,
  depth: 600,
  material: 'Белый',
  shelves: [],
  drawers: [],
  baseType: 'plinth',
  backType: 'groove'
};

const CabinetContext = createContext<CabinetContextType | undefined>(undefined);

export const CabinetProvider: React.FC<{ children: ReactNode; initialParams?: CabinetParams }> = ({ children, initialParams }) => {
  const { state: params, set: setParams, undo, redo, canUndo, canRedo, clear } = useHistory<CabinetParams>(initialParams || DEFAULT_PARAMS);
  const { addToast } = useProjectStore();

  // Sync if initialParams changes deeply (optional, usually component remounts)
  useEffect(() => {
      if (initialParams) clear(initialParams);
  }, [initialParams, clear]);

  const updateParams = useCallback((changes: Partial<CabinetParams>) => {
    setParams({ ...params, ...changes });
  }, [params, setParams]);

  const addShelf = useCallback((y?: number) => {
    const TH = 16; // Shelf Thickness
    const MIN_GAP_REQUIRED = 50; // Minimum gap to even consider placing a shelf

    let positionY = y;

    // --- SMART POSITIONING ALGORITHM ---
    if (positionY === undefined) {
        const baseH = params.baseType === 'legs' ? 100 : 70;
        
        // 1. Define Boundaries
        // Floor occupied zone: 0 to (Base Height + Bottom Panel Thickness)
        const bottomBoundary = baseH + TH; 
        
        // Ceiling occupied zone: (Cabinet Height - Roof Panel Thickness) to Height
        const topBoundary = params.height - TH;

        // 2. Collect all vertical occupants (Start Y, End Y)
        const occupants = [
            { start: 0, end: bottomBoundary },       // Bottom Zone
            { start: topBoundary, end: params.height } // Top Zone
        ];

        // Add existing shelves
        params.shelves.forEach(s => occupants.push({ start: s.y, end: s.y + TH }));
        
        // Add existing drawers
        params.drawers.forEach(d => occupants.push({ start: d.y, end: d.y + d.height }));

        // 3. Sort by position
        occupants.sort((a, b) => a.start - b.start);

        // 4. Find the largest gap
        let maxGap = 0;
        let bestY = -1;

        for (let i = 0; i < occupants.length - 1; i++) {
            const current = occupants[i];
            const next = occupants[i+1];

            const gapStart = current.end; 
            const gapEnd = next.start;    
            const gapSize = gapEnd - gapStart;

            // Check if gap fits minimum requirement (Shelf + Air)
            // gapSize must accommodate 16mm shelf + MIN_GAP_REQUIRED? 
            // Or gapSize itself > 50mm? User specified "gap > 50mm minimum".
            // We use strict check: gap must be at least 50mm to fit anything useful.
            if (gapSize > MIN_GAP_REQUIRED) {
                if (gapSize > maxGap) {
                    maxGap = gapSize;
                    // Position at center of gap:
                    // Center = gapStart + (gapSize / 2)
                    // Adjust for shelf thickness: Y = Center - (TH / 2)
                    bestY = gapStart + (gapSize / 2) - (TH / 2);
                }
            }
        }

        // 5. Safety Fallback
        if (bestY === -1) {
            addToast("Нет свободного места > 50мм для новой полки!", "error");
            return; // PREVENT ADDING
        }

        positionY = Math.round(bestY);
    } 
    else {
        // Manual Positioning Validation
        const manualTop = positionY + TH;
        // Check collisions with existing items
        const hasCollision = [...params.shelves, ...params.drawers].some(item => {
            const h = 'height' in item ? item.height : TH;
            const itemTop = item.y + h;
            // Intersection: (StartA <= EndB) and (EndA >= StartB)
            return (positionY! < itemTop && manualTop > item.y);
        });

        if (hasCollision) {
             addToast("Ошибка: Наложение на существующую деталь", "error");
             return;
        }
        
        // Check boundaries
        if (positionY < (params.baseType === 'legs' ? 100 : 70) + TH || positionY > params.height - TH - TH) {
             addToast("Ошибка: Выход за границы корпуса", "error");
             return;
        }
    }
    
    // Add Shelf
    const newShelf = {
        id: `sh-${Date.now()}`,
        y: positionY,
        x: 0,
        width: params.width - 32, // Standard inset
        depth: params.depth - 20,
        type: 'открытая' as const
    };
    
    updateParams({ shelves: [...params.shelves, newShelf] });
    addToast(`Полка добавлена на высоту ${positionY}мм`, "success");

  }, [params, updateParams, addToast]);

  const addDrawer = useCallback((y: number) => {
    const newDrawer = {
        id: `dr-${Date.now()}`,
        y,
        x: 0,
        width: params.width - 32,
        height: 200,
        depth: params.depth - 50,
        handles: true
    };
    updateParams({ drawers: [...params.drawers, newDrawer] });
  }, [params, updateParams]);

  const removeItem = useCallback((id: string, type: 'shelf' | 'drawer') => {
    updateParams({
      shelves: type === 'shelf' ? params.shelves.filter(s => s.id !== id) : params.shelves,
      drawers: type === 'drawer' ? params.drawers.filter(d => d.id !== id) : params.drawers,
    });
  }, [params, updateParams]);

  const setMaterial = useCallback((mat: CabinetMaterialType) => {
      updateParams({ material: mat });
  }, [updateParams]);

  return (
    <CabinetContext.Provider value={{ 
        params, updateParams, addShelf, addDrawer, removeItem, setMaterial,
        undo, redo, canUndo, canRedo
    }}>
      {children}
    </CabinetContext.Provider>
  );
};

export const useCabinet = () => {
  const context = useContext(CabinetContext);
  if (!context) {
    throw new Error('useCabinet must be used within a CabinetProvider');
  }
  return context;
};
