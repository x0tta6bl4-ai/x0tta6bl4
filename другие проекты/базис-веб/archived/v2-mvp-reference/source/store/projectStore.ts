
import { create } from 'zustand';
import { Panel, Layer, Material, Axis, TextureType, ProductionStatus, ProductionStage } from '../types';

interface Toast {
  id: string;
  message: string;
  type: 'info' | 'success' | 'error';
}

interface ProjectState {
  panels: Panel[];
  layers: Layer[];
  selectedPanelId: string | null;
  history: Panel[][];
  historyIndex: number;
  toasts: Toast[];
  
  // Pipeline State
  currentGlobalStage: ProductionStage;
  
  // Actions
  setPanels: (panels: Panel[]) => void;
  addPanel: (panel: Panel) => void;
  updatePanel: (id: string, changes: Partial<Panel>) => void;
  bulkUpdatePanels: (updates: { id: string; changes: Partial<Panel> }[]) => void;
  deletePanel: (id: string) => void;
  duplicatePanel: (id: string) => void;
  selectPanel: (id: string | null, multi?: boolean) => void;
  
  // Manufacturing Actions
  setGlobalStage: (stage: ProductionStage) => void;
  setPanelStatus: (id: string, status: ProductionStatus) => void;
  advancePanelStage: (id: string) => void;
  
  // History
  undo: () => void;
  redo: () => void;
  pushHistory: (panels: Panel[]) => void;
  
  // UI
  addToast: (message: string, type?: Toast['type']) => void;
  removeToast: (id: string) => void;
}

// Initial Data
const INITIAL_LAYERS: Layer[] = [
    { id: 'body', name: 'Корпус (ЛДСП)', visible: true, locked: false, color: '#FFFFFF' },
    { id: 'facade', name: 'Фасады', visible: true, locked: false, color: '#FF0000' },
    { id: 'back', name: 'Задние стенки', visible: true, locked: false, color: '#FFFF00' },
    { id: 'shelves', name: 'Полки', visible: true, locked: false, color: '#00FF00' },
];

const STAGE_FLOW: ProductionStage[] = ['design', 'cutting', 'edging', 'drilling', 'assembly', 'quality_control', 'shipping'];

export const useProjectStore = create<ProjectState>((set, get) => ({
  panels: [],
  layers: INITIAL_LAYERS,
  selectedPanelId: null,
  history: [[]],
  historyIndex: 0,
  toasts: [],
  currentGlobalStage: 'design',

  setPanels: (panels) => {
    // Ensure status fields exist
    const withStatus = panels.map(p => ({
        ...p, 
        productionStatus: p.productionStatus || 'pending',
        currentStage: p.currentStage || 'design'
    }));
    set({ panels: withStatus });
    get().pushHistory(withStatus);
  },

  addPanel: (panel) => {
    const newPanel = { ...panel, productionStatus: 'pending' as ProductionStatus, currentStage: 'design' as ProductionStage };
    const newPanels = [...get().panels, newPanel];
    set({ panels: newPanels });
    get().pushHistory(newPanels);
  },

  updatePanel: (id, changes) => {
    const newPanels = get().panels.map((p) => (p.id === id ? { ...p, ...changes } : p));
    set({ panels: newPanels });
    get().pushHistory(newPanels);
  },

  bulkUpdatePanels: (updates) => {
    let newPanels = [...get().panels];
    updates.forEach((u) => {
      newPanels = newPanels.map((p) => (p.id === u.id ? { ...p, ...u.changes } : p));
    });
    set({ panels: newPanels });
    get().pushHistory(newPanels);
  },

  deletePanel: (id) => {
    const newPanels = get().panels.filter((p) => p.id !== id && !p.isSelected);
    set({ panels: newPanels, selectedPanelId: null });
    get().pushHistory(newPanels);
    get().addToast('Деталь удалена', 'info');
  },

  duplicatePanel: (id) => {
    const source = get().panels.find((p) => p.id === id);
    if (!source) return;
    const newPanel = {
      ...source,
      id: `p-${Date.now()}`,
      x: source.x + 20,
      y: source.y + 20,
      isSelected: true,
      productionStatus: 'pending' as ProductionStatus,
      currentStage: 'design' as ProductionStage,
      name: `${source.name} (Копия)`
    };
    const newPanels = [...get().panels.map(p => ({...p, isSelected: false})), newPanel];
    set({ panels: newPanels, selectedPanelId: newPanel.id });
    get().pushHistory(newPanels);
    get().addToast('Деталь дублирована', 'success');
  },

  selectPanel: (id, multi = false) => {
    set((state) => ({
      selectedPanelId: id,
      panels: state.panels.map((p) => ({
        ...p,
        isSelected: multi ? (p.id === id ? !p.isSelected : p.isSelected) : p.id === id,
      })),
    }));
  },

  // Manufacturing Actions
  setGlobalStage: (stage) => {
      set({ currentGlobalStage: stage });
  },

  setPanelStatus: (id, status) => {
      set(state => ({
          panels: state.panels.map(p => p.id === id ? { ...p, productionStatus: status } : p)
      }));
  },

  advancePanelStage: (id) => {
      set(state => {
          const newPanels = state.panels.map(p => {
              if (p.id === id) {
                  const currentIdx = STAGE_FLOW.indexOf(p.currentStage || 'design');
                  const nextStage = STAGE_FLOW[Math.min(currentIdx + 1, STAGE_FLOW.length - 1)];
                  return { 
                      ...p, 
                      currentStage: nextStage,
                      productionStatus: 'pending' as ProductionStatus 
                  };
              }
              return p;
          });
          return { panels: newPanels };
      });
  },

  // History Implementation
  pushHistory: (panels) => {
    set((state) => {
      const newHistory = state.history.slice(0, state.historyIndex + 1);
      newHistory.push(panels);
      if (newHistory.length > 50) newHistory.shift();
      return {
        history: newHistory,
        historyIndex: newHistory.length - 1,
      };
    });
  },

  undo: () => {
    const { history, historyIndex } = get();
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      set({
        panels: history[newIndex],
        historyIndex: newIndex,
      });
      get().addToast('Отмена действия', 'info');
    }
  },

  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      set({
        panels: history[newIndex],
        historyIndex: newIndex,
      });
      get().addToast('Повтор действия', 'info');
    }
  },

  addToast: (message, type = 'info') => {
    const id = Math.random().toString(36).substr(2, 9);
    set((state) => ({ toasts: [...state.toasts, { id, message, type }] }));
    setTimeout(() => get().removeToast(id), 3000);
  },

  removeToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
}));
