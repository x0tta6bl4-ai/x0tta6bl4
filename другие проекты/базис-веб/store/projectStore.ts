import { create } from 'zustand';
import { Panel, Layer, Material, Axis, TextureType, ProductionStatus, ProductionStage } from '../types';
import { validatePanelUpdate } from '../validators';
import { Assembly, BOMHierarchy, DFMReport, FEAResult, OptimizationResult } from '../types/CADTypes';

interface Toast {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
}

interface ProjectState {
  panels: Panel[];
  layers: Layer[];
  selectedPanelId: string | null;
  history: Panel[][];
  historyIndex: number;
  toasts: Toast[];
  
  // CAD Data Fields
  solvedAssembly: Assembly | null;
  bomData: BOMHierarchy | null;
  dfmReport: DFMReport | null;
  feaResults: FEAResult | null;
  optimizationResults: OptimizationResult | null;
  
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
  
  // CAD Actions
  setSolvedAssembly: (assembly: Assembly | null) => void;
  setBOMData: (bom: BOMHierarchy | null) => void;
  setDFMReport: (report: DFMReport | null) => void;
  setFEAResults: (results: FEAResult | null) => void;
  setOptimizationResults: (results: OptimizationResult | null) => void;
  clearCADData: () => void;
}

// Initial Data
const INITIAL_LAYERS: Layer[] = [
    { id: 'body', name: 'Корпус (ЛДСП)', visible: true, locked: false, color: '#FFFFFF' },
    { id: 'facade', name: 'Фасады', visible: true, locked: false, color: '#FF0000' },
    { id: 'back', name: 'Задние стенки', visible: true, locked: false, color: '#FFFF00' },
    { id: 'shelves', name: 'Полки', visible: true, locked: false, color: '#00FF00' },
];

const STAGE_FLOW: ProductionStage[] = ['design', 'cutting', 'edging', 'drilling', 'assembly', 'quality_control', 'shipping'];

// Demo Panels
const INITIAL_PANELS: Panel[] = [
  {
    id: 'p-1',
    name: 'Боковая стенка левая',
    layer: 'body',
    x: 0,
    y: 0,
    z: 0,
    width: 600,
    height: 2000,
    depth: 16,
    rotation: Axis.Z,
    materialId: 'ldsp-oak',
    color: '#D2B48C',
    texture: TextureType.NONE,
    textureRotation: 0,
    visible: true,
    isSelected: false,
    openingType: 'none',
    hardware: [],
    edging: { top: 'none', bottom: 'none', left: 'none', right: 'none' },
    groove: { enabled: false, side: 'top', width: 0, depth: 0, offset: 0 },
    productionStatus: 'pending',
    currentStage: 'design',
  },
  {
    id: 'p-2',
    name: 'Боковая стенка правая',
    layer: 'body',
    x: 1200,
    y: 0,
    z: 0,
    width: 600,
    height: 2000,
    depth: 16,
    rotation: Axis.Z,
    materialId: 'ldsp-oak',
    color: '#D2B48C',
    texture: TextureType.NONE,
    textureRotation: 0,
    visible: true,
    isSelected: false,
    openingType: 'none',
    hardware: [],
    edging: { top: 'none', bottom: 'none', left: 'none', right: 'none' },
    groove: { enabled: false, side: 'top', width: 0, depth: 0, offset: 0 },
    productionStatus: 'pending',
    currentStage: 'design',
  },
  {
    id: 'p-3',
    name: 'Верхняя полка',
    layer: 'shelves',
    x: 0,
    y: 1900,
    z: 0,
    width: 1800,
    height: 600,
    depth: 16,
    rotation: Axis.Z,
    materialId: 'ldsp-oak',
    color: '#90EE90',
    texture: TextureType.NONE,
    textureRotation: 0,
    visible: true,
    isSelected: false,
    openingType: 'none',
    hardware: [],
    edging: { top: 'none', bottom: 'none', left: 'none', right: 'none' },
    groove: { enabled: false, side: 'top', width: 0, depth: 0, offset: 0 },
    productionStatus: 'pending',
    currentStage: 'design',
  },
  {
    id: 'p-4',
    name: 'Нижняя полка',
    layer: 'shelves',
    x: 0,
    y: 900,
    z: 0,
    width: 1800,
    height: 600,
    depth: 16,
    rotation: Axis.Z,
    materialId: 'ldsp-oak',
    color: '#90EE90',
    texture: TextureType.NONE,
    textureRotation: 0,
    visible: true,
    isSelected: false,
    openingType: 'none',
    hardware: [],
    edging: { top: 'none', bottom: 'none', left: 'none', right: 'none' },
    groove: { enabled: false, side: 'top', width: 0, depth: 0, offset: 0 },
    productionStatus: 'pending',
    currentStage: 'design',
  },
];

export const useProjectStore = create<ProjectState>((set, get) => ({
  panels: INITIAL_PANELS,
  layers: INITIAL_LAYERS,
  selectedPanelId: null,
  history: [[]],
  historyIndex: 0,
  toasts: [],
  currentGlobalStage: 'design',
  
  // CAD Data
  solvedAssembly: null,
  bomData: null,
  dfmReport: null,
  feaResults: null,
  optimizationResults: null,

  setPanels: (panels) => {
    // Ensure status fields exist + apply safe runtime defaults
    const toFiniteNumber = (v: any, fallback: number) => {
      const n = typeof v === 'number' ? v : Number(v);
      return Number.isFinite(n) ? n : fallback;
    };
    const minPositive = (v: number, fallback: number) => (v > 0 ? v : fallback);

    const withStatus = panels.map(p => {
      const x = toFiniteNumber((p as any).x, 0);
      const y = toFiniteNumber((p as any).y, 0);
      const z = toFiniteNumber((p as any).z, 0);
      const width = minPositive(toFiniteNumber((p as any).width, 1), 1);
      const height = minPositive(toFiniteNumber((p as any).height, 1), 1);
      const depth = minPositive(toFiniteNumber((p as any).depth, 16), 1);

      return {
        ...p,
        x,
        y,
        z,
        width,
        height,
        depth,
        rotation: (p as any).rotation ?? Axis.Z,
        texture: (p as any).texture ?? TextureType.NONE,
        textureRotation: (p as any).textureRotation ?? 0,
        visible: (p as any).visible ?? true,
        layer: (p as any).layer ?? 'body',
        color: (p as any).color ?? '#D2B48C',
        openingType: (p as any).openingType ?? 'none',
        edging: (p as any).edging ?? { top: 'none', bottom: 'none', left: 'none', right: 'none' },
        groove: (p as any).groove ?? { enabled: false, side: 'top', width: 0, depth: 0, offset: 0 },
        hardware: (p as any).hardware ?? [],
        productionStatus: (p as any).productionStatus || 'pending',
        currentStage: (p as any).currentStage || 'design'
      };
    });
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
    const errors = validatePanelUpdate(changes);
    if (errors.length > 0) {
      errors.forEach(err => {
        get().addToast(err.message, 'error');
      });
      return;
    }
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
  // CAD Actions
  setSolvedAssembly: (assembly) => {
    set({ solvedAssembly: assembly });
  },

  setBOMData: (bom) => {
    set({ bomData: bom });
  },

  setDFMReport: (report) => {
    set({ dfmReport: report });
  },

  setFEAResults: (results) => {
    set({ feaResults: results });
  },

  setOptimizationResults: (results) => {
    set({ optimizationResults: results });
  },

  clearCADData: () => {
    set({
      solvedAssembly: null,
      bomData: null,
      dfmReport: null,
      feaResults: null,
      optimizationResults: null
    });
  },
}));
