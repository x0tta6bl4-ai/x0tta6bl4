import React, { useState, useRef, useCallback, Suspense, lazy } from 'react';
import { CabinetConfig, Section, CabinetItem } from '../../types';
import VisualEditor from './VisualEditor';
import { PropertiesPanel } from './PropertiesPanel';
import { ToolsPanel } from './ToolsPanel';
import { useCabinetWizard } from '../../hooks/useCabinetWizard';
import { CabinetGenerator } from '../../services/CabinetGenerator';
const Scene3D = lazy(() => import('../Scene3D'));
import { Eye, RefreshCw } from 'lucide-react';

interface CabinetWizardProps {
  materialLibrary: any[];
  onGenerate: (panels: any[]) => void;
  initialState?: { config: CabinetConfig; sections: Section[] };
}

export const CabinetWizard: React.FC<CabinetWizardProps> = ({
  materialLibrary,
  onGenerate,
  initialState
}) => {
  const {
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
  } = useCabinetWizard(initialState);

  const generatorRef = useRef<CabinetGenerator | null>(null);
  const [show3DPreview, setShow3DPreview] = useState(false);
  const [previewPanels, setPreviewPanels] = useState<any[]>([]);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);

  const generatePreview = useCallback(async () => {
    setIsGeneratingPreview(true);
    try {
      const generator = new CabinetGenerator(config, sections, materialLibrary);
      const panels = generator.generate();
      setPreviewPanels(panels);
      generatorRef.current = generator;
    } catch (error) {
      console.error('[Wizard Preview] Generation error:', error);
    } finally {
      setIsGeneratingPreview(false);
    }
  }, [config, sections, materialLibrary]);

  const handleGenerate = async () => {
    try {
      console.log('[Wizard] Generating cabinet with:', {
        config,
        sectionsCount: sections.length,
        totalItems: sections.reduce((sum, sec) => sum + sec.items.length, 0)
      });

      const generator = new CabinetGenerator(config, sections, materialLibrary);
      generatorRef.current = generator;

      const validation = generator.validate();
      if (!validation.valid) {
        console.warn('[Wizard] Validation errors:', validation.errors);
      }

      const panels = generator.generate();
      
      console.log('[Wizard] Generated panels:', panels.length, panels[0]);
      
      if (!panels || panels.length === 0) {
        console.error('[Wizard] Generator returned empty panels');
        alert('Генерация не удалась: генератор вернул пустой список панелей');
        return;
      }

      onGenerate(panels);
    } catch (error) {
      console.error('[Wizard] Generation error:', error);
      alert(`Ошибка генерации: ${error instanceof Error ? error.message : 'Н неизвестная ошибка'}`);
    }
  };

  return (
    <div className="flex h-full bg-[#151515] overflow-hidden">
      {/* Tools Panel */}
      <ToolsPanel
        onAddItem={handleAddItem}
        onAddSection={handleAddSection}
        onDelete={handleDeleteSelected}
        hasSelection={!!selectedItemId}
      />

      {/* Main Content Area */}
      {show3DPreview ? (
        <div className="flex-1 relative">
          <div className="absolute top-4 left-4 z-50 bg-black/90 p-2 rounded-lg border border-gray-600">
            <button
              onClick={() => setShow3DPreview(false)}
              className="flex items-center gap-2 px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 rounded text-white font-semibold transition-colors"
            >
              <Eye size={16} />
              Переключить на 2D
            </button>
            <button
              onClick={generatePreview}
              disabled={isGeneratingPreview}
              className="mt-2 flex items-center gap-2 px-3 py-1 text-sm bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded text-white font-semibold transition-colors"
            >
              <RefreshCw size={16} className={isGeneratingPreview ? 'animate-spin' : ''} />
              Обновить предпросмотр
            </button>
          </div>
          {previewPanels.length > 0 ? (
            <Suspense fallback={
              <div className="w-full h-full flex items-center justify-center bg-slate-950">
                <div className="text-center text-slate-400">
                  <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                  <p className="text-sm">Загрузка 3D...</p>
                </div>
              </div>
            }>
              <Scene3D previewMode panels={previewPanels} />
            </Suspense>
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-slate-950">
              <div className="text-center text-slate-400">
                <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                <p className="text-sm">Генерация 3D-предпросмотра...</p>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 relative">
          <div className="absolute top-4 left-4 z-50 bg-black/90 p-2 rounded-lg border border-gray-600">
            <button
              onClick={() => {
                setShow3DPreview(true);
                generatePreview();
              }}
              className="flex items-center gap-2 px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 rounded text-white font-semibold transition-colors"
            >
              <Eye size={16} />
              Переключить на 3D
            </button>
          </div>
          <VisualEditor
            config={config}
            sections={sections}
            selectedSectionId={selectedSectionId}
            selectedItemId={selectedItemId}
            showDoors={showDoors}
            onSelectSection={handleSelectSection}
            onSelectItem={handleSelectItem}
            onMoveItem={handleMoveItem}
            onResizeSection={handleResizeSection}
          />
        </div>
      )}

      {/* Properties Panel */}
      <PropertiesPanel
        activeTab={selectedItemId ? 'item' : 'global'}
        onTabChange={() => {}}
        config={config}
        onConfigChange={handleConfigChange}
        sections={sections}
        selectedItemId={selectedItemId}
        selectedSectionId={selectedSectionId}
        onDistributeItems={handleDistributeItems}
        onUpdateItem={handleUpdateItem}
        onGenerate={handleGenerate}
      />
    </div>
  );
};
