import React from 'react';
import { Panel, Material } from '../types';
import { CabinetGenerator, checkCollisions } from '../services/CabinetGenerator';
import { AlertTriangle, DoorOpen } from 'lucide-react';
import { useCabinetWizardState } from '../hooks/useCabinetWizardState';
import { useSectionManagement } from '../hooks/useSectionManagement';
import VisualEditor from './CabinetWizard/VisualEditor';
import { ToolsPanel } from './CabinetWizard/ToolsPanel';
import { PropertiesPanel } from './CabinetWizard/PropertiesPanel';

interface CabinetWizardProps {
  onGenerate: (panels: Panel[]) => void;
  materialLibrary: Material[];
  initialState?: { config: any; sections: any } | null;
}

const CabinetWizardComponent: React.FC<CabinetWizardProps> = ({
  onGenerate,
  materialLibrary,
  initialState,
}) => {
  const state = useCabinetWizardState(initialState);
  const sectionMgmt = useSectionManagement({
    sections: state.sections,
    setSections: state.setSections,
    config: state.config,
  });

  const generate = () => {
    const inputErrors: string[] = [];
    if (!state.config.width || state.config.width <= 0) {
      inputErrors.push('Не указана ширина изделия');
    }
    if (!state.config.height || state.config.height <= 0) {
      inputErrors.push('Не указана высота изделия');
    }
    if (!state.config.depth || state.config.depth <= 0) {
      inputErrors.push('Не указана глубина изделия');
    }

    if (inputErrors.length > 0) {
      state.setErrors(inputErrors);
      return;
    }

    const generator = new CabinetGenerator(
      state.config,
      state.sections,
      materialLibrary
    );
    const validation = generator.validate();
    if (!validation.valid) {
      state.setErrors(validation.errors);
      return;
    }
    state.setErrors([]);
    const panels = generator.generate();

    const collisions = checkCollisions(panels);
    if (collisions.length > 0) {
      state.setErrors(collisions);
    }

    onGenerate(panels);
  };

  return (
    <div className="flex h-full bg-[#111] text-slate-300 overflow-hidden font-sans">
      {/* LEFT: TOOLS */}
      <ToolsPanel
        onAddItem={(type) => sectionMgmt.addItem(type, state.selectedSectionId)}
        onAddSection={sectionMgmt.addSection}
        onDelete={() => {
          if (state.selectedItemId) {
            sectionMgmt.deleteItem(state.selectedItemId);
            state.setSelectedItemId(null);
          } else {
            sectionMgmt.removeSection();
            state.setSelectedSectionId(0);
          }
        }}
        hasSelection={!!state.selectedItemId}
      />

      {/* CENTER: VISUAL EDITOR */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#1e1e1e]">
        <div className="h-12 bg-[#252526] border-b border-[#333] flex items-center justify-between px-6 shrink-0 shadow-md z-30">
          <div className="flex items-center gap-3">
            <div className="bg-blue-600/20 p-1.5 rounded text-blue-500">
              <DoorOpen size={16} />
            </div>
            <div>
              <div className="text-xs font-bold text-white uppercase tracking-wider">Конструктор</div>
              <div className="text-[10px] text-slate-500 font-mono">Сетка: 32мм</div>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => state.setShowDoors(!state.showDoors)}
              className={`px-3 py-1.5 rounded flex items-center gap-2 text-xs font-bold transition ${
                state.showDoors
                  ? 'bg-slate-700 text-white'
                  : 'bg-[#333] text-slate-500 hover:text-white'
              }`}
            >
              <DoorOpen size={16} /> {state.showDoors ? 'Скрыть фасады' : 'Показать фасады'}
            </button>
          </div>
        </div>

        {state.errors.length > 0 && (
          <div className="absolute top-14 left-4 right-4 z-50 bg-red-900/90 backdrop-blur border border-red-500/50 rounded-lg p-3 flex items-start gap-3 shadow-2xl animate-in slide-in-from-top-2 max-h-[30vh] overflow-y-auto">
            <AlertTriangle size={20} className="text-red-400 mt-0.5 shrink-0" />
            <div className="flex-1">
              <h4 className="text-xs font-bold text-red-100 mb-1">
                Обнаружены проблемы ({state.errors.length})
              </h4>
              <ul className="list-disc list-inside text-[11px] text-red-200">
                {state.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
            <button
              onClick={() => state.setErrors([])}
              className="hover:bg-red-800 rounded p-1 text-red-200"
            >
              ✕
            </button>
          </div>
        )}

        <VisualEditor
          config={state.config}
          sections={state.sections}
          selectedSectionId={state.selectedSectionId}
          selectedItemId={state.selectedItemId}
          showDoors={state.showDoors}
          onSelectSection={(id) => {
            state.setSelectedSectionId(id);
            state.setSelectedItemId(null);
          }}
          onSelectItem={state.setSelectedItemId}
          onMoveItem={(id, secIdx, y) => {
            const item = state.sections.flatMap(s => s.items).find(i => i.id === id);
            if (item) {
              const next = state.sections.map(s => ({
                ...s,
                items: s.items.filter(i => i.id !== id),
              }));
              if (next[secIdx]) {
                next[secIdx].items.push({ ...item, y });
              }
              state.setSections(next);
            }
          }}
          onResizeSection={sectionMgmt.handleResizeSection}
        />
      </div>

      {/* RIGHT: PROPERTIES */}
      <PropertiesPanel
        activeTab={state.activeTab}
        onTabChange={state.setActiveTab}
        config={state.config}
        onConfigChange={state.setConfig}
        sections={state.sections}
        selectedItemId={state.selectedItemId}
        selectedSectionId={state.selectedSectionId}
        onDistributeItems={() => sectionMgmt.distributeItems(state.selectedSectionId)}
        onUpdateItem={sectionMgmt.updateItem}
        onGenerate={generate}
      />
    </div>
  );
};

export const CabinetWizard = React.memo(CabinetWizardComponent);
