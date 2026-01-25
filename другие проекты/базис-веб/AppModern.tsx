import React, { useState, useEffect, Suspense } from 'react';
import { useProjectStore } from './store/projectStore';
import { Panel, Axis, TextureType } from './types';
import { MATERIAL_LIBRARY } from './materials.config';
import { DEFAULT_CABINET_CONFIG } from './constants';

// Import UI Components
import {
  NavigationBar,
  Toolbar,
  SidePanel,
  PropertiesPanel,
  MainLayout,
  StatusBar,
  CanvasEditor,
  FileDialog,
  SettingsDialog
} from './components/UI';

// Dynamic Views (for bundle optimization)
const Scene3D = React.lazy(() => import('./components/Scene3D'));
const Scene3DBabylon = React.lazy(() => import('./components/Scene3DBabylon'));
const NestingView = React.lazy(() => import('./components/NestingView'));

// Static Views
import { CabinetWizard } from './components/CabinetWizard';
import EditorPanel from './components/EditorPanel';
import ParametricEditor from './components/ParametricEditor';
import ToastProvider from './components/ToastProvider';
import ErrorBoundary from './components/ErrorBoundary';
import AIAssistant from './components/AIAssistant';
import { initializeGemini } from './services/geminiService';

enum ViewMode {
  DESIGN = 'design',
  WIZARD = 'wizard',
  SCRIPT = 'script',
  CUT_LIST = 'cut_list',
  DRAWING = 'drawing',
  NESTING = 'nesting',
  PRODUCTION = 'production',
  CAD_SOLVER = 'cad_solver',
  CAD_BOM = 'cad_bom',
  CAD_DFM = 'cad_dfm'
}

const AppModern: React.FC = () => {
  // State Management
  const [viewMode, setViewMode] = useState<ViewMode>(ViewMode.WIZARD);
  const [zoom, setZoom] = useState(100);
  const [gridSize, setGridSize] = useState(50);
  const [showGrid, setShowGrid] = useState(true);
  const [projectName, setProjectName] = useState('Мой проект');
  const [isDirty, setIsDirty] = useState(false);

  // UI Dialogs
  const [showFileDialog, setShowFileDialog] = useState(false);
  const [showSettingsDialog, setShowSettingsDialog] = useState(false);
  const [show3DView, setShow3DView] = useState(true);
  const [engine3D, setEngine3D] = useState<'three' | 'babylon'>('three');

  // Store
  const {
    panels,
    setPanels,
    updatePanel,
    deletePanel,
    selectPanel,
    undo,
    redo,
    layers,
    selectedPanelId,
    addToast
  } = useProjectStore();

  // Initialize
  useEffect(() => {
    const apiKey = import.meta.env.VITE_GEMINI_API_KEY;
    if (apiKey) {
      initializeGemini(apiKey);
    }
  }, []);

  // Auto-save
  useEffect(() => {
    if (panels.length > 0) {
      localStorage.setItem('bazis_project_current', JSON.stringify({ panels, projectName }));
      setIsDirty(true);
    }
  }, [panels, projectName]);

  // Handlers
  const handleSave = () => {
    const data = { panels, projectName, timestamp: Date.now() };
    localStorage.setItem(`bazis_project_${projectName}`, JSON.stringify(data));
    setIsDirty(false);
    addToast(`✓ Сохранено: ${projectName}`, 'success');
  };

  const handleLoad = (filename: string) => {
    const data = localStorage.getItem(`bazis_project_${filename}`);
    if (data) {
      const project = JSON.parse(data);
      setPanels(project.panels);
      setProjectName(project.projectName);
      setIsDirty(false);
      addToast(`✓ Загружено: ${filename}`, 'success');
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
      e.preventDefault();
      undo();
    } else if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
      e.preventDefault();
      redo();
    } else if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Delete' && selectedPanelId) {
      e.preventDefault();
      deletePanel(selectedPanelId);
    }
  };

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedPanelId]);

  const selectedPanel = panels.find((p) => p.id === selectedPanelId) || null;

  return (
    <>
      <ToastProvider />

      {/* File Dialog */}
      <FileDialog
        isOpen={showFileDialog}
        onClose={() => setShowFileDialog(false)}
        onSave={handleSave}
        onLoad={handleLoad}
        recentFiles={[
          'Шкаф простой',
          'Модульная система',
          'Кухонный гарнитур',
          'Встроенный шкаф'
        ]}
      />

      {/* Settings Dialog */}
      <SettingsDialog
        isOpen={showSettingsDialog}
        onClose={() => setShowSettingsDialog(false)}
        settings={{
          theme: 'dark',
          showGrid: showGrid,
          snapToGrid: true,
          autoSave: true,
          autoSaveInterval: 30
        }}
        onSettingsChange={(newSettings) => {
          setShowGrid(newSettings.showGrid);
        }}
      />

      <MainLayout
        navBar={
          <NavigationBar
            projectName={projectName}
            menuOpen={viewMode !== ViewMode.DESIGN}
            onMenuToggle={() => {}}
            onSave={handleSave}
            onLoad={() => setShowFileDialog(true)}
            onSettings={() => setShowSettingsDialog(true)}
            isDirty={isDirty}
          />
        }
        toolbar={
          <Toolbar
            onUndo={undo}
            onRedo={redo}
            onDelete={() => selectedPanelId && deletePanel(selectedPanelId)}
            onCopy={() => addToast('Функция копирования будет реализована', 'info')}
            onPaste={() => addToast('Функция вставки будет реализована', 'info')}
            onSave={handleSave}
            canUndo={true}
            canRedo={true}
            hasSelection={!!selectedPanelId}
            canPaste={false}
            onToggleGrid={() => setShowGrid(!showGrid)}
            onToggle3D={() => setShow3DView(!show3DView)}
            view3DEnabled={show3DView}
          />
        }
        sidePanel={
          <SidePanel
            layers={layers}
            panels={panels}
            selectedPanelId={selectedPanelId}
            onSelectPanel={selectPanel}
            onToggleLayerVisibility={(id) => {
              addToast('Layer visibility toggle - будет реализовано', 'info');
            }}
            onToggleLayerLocked={(id) => {
              addToast('Layer lock toggle - будет реализовано', 'info');
            }}
            onDeletePanel={deletePanel}
            onRenamePanel={(id, name) => {
              updatePanel(id, { name });
            }}
          />
        }
        rightPanel={
          <PropertiesPanel
            selectedPanel={selectedPanel}
            onPanelUpdate={(id, changes) => updatePanel(id, changes)}
            materials={MATERIAL_LIBRARY}
          />
        }
        mainContent={
          <ErrorBoundary>
            {viewMode === ViewMode.WIZARD && (
              <CabinetWizard
                materialLibrary={MATERIAL_LIBRARY}
                onGenerate={(panels) => {
                  if (panels && panels.length > 0) {
                    setPanels(panels);
                    setViewMode(ViewMode.DESIGN);
                    addToast(`✓ Сгенерировано ${panels.length} панелей`, 'success');
                  }
                }}
              />
            )}

            {viewMode === ViewMode.DESIGN && (
              <div className="w-full h-full flex gap-0">
                <div className="flex-1 relative">
                  {show3DView && (
                    <Suspense fallback={
                      <div className="w-full h-full flex items-center justify-center bg-slate-950">
                        <div className="text-center text-slate-400">
                          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                          <p className="text-sm">Loading 3D engine...</p>
                        </div>
                      </div>
                    }>
                      {engine3D === 'babylon' ? <Scene3DBabylon /> : <Scene3D />}
                    </Suspense>
                  )}

                  {/* 3D Engine Switcher */}
                  <div className="absolute top-20 left-4 z-50 bg-black/90 p-3 rounded-lg border border-gray-600 shadow-xl">
                    <button
                      onClick={() => setEngine3D(engine3D === 'babylon' ? 'three' : 'babylon')}
                      className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-semibold"
                    >
                      {engine3D === 'babylon' ? 'Babylon.js' : 'Three.js'}
                    </button>
                  </div>
                </div>

                {/* 2D Canvas Editor */}
                {!show3DView && (
                  <div className="flex-1">
                    <CanvasEditor
                      panels={panels}
                      selectedPanelId={selectedPanelId}
                      onSelectPanel={selectPanel}
                      onUpdatePanel={(id, changes) => updatePanel(id, changes)}
                      zoom={zoom}
                      onZoomChange={setZoom}
                      gridSize={gridSize}
                      showGrid={showGrid}
                    />
                  </div>
                )}

                {/* Parametric Editor */}
                <div className="w-80 shrink-0 overflow-hidden border-l border-slate-700">
                  <ParametricEditor selectedPanel={selectedPanel} />
                </div>
              </div>
            )}

            {/* Placeholder Views */}
            {viewMode === ViewMode.CUT_LIST && (
              <div className="w-full h-full flex items-center justify-center">
                <div className="text-center text-slate-400">
                  <h2 className="text-xl font-bold mb-2">Смета материалов</h2>
                  <p className="text-sm">Coming soon</p>
                </div>
              </div>
            )}

            {viewMode === ViewMode.CAD_BOM && (
              <div className="w-full h-full flex items-center justify-center">
                <div className="text-center text-slate-400">
                  <h2 className="text-xl font-bold mb-2">Bill of Materials</h2>
                  <p className="text-sm">Coming soon</p>
                </div>
              </div>
            )}

            {viewMode === ViewMode.CAD_DFM && (
              <div className="w-full h-full flex items-center justify-center">
                <div className="text-center text-slate-400">
                  <h2 className="text-xl font-bold mb-2">DFM Analysis</h2>
                  <p className="text-sm">Coming soon</p>
                </div>
              </div>
            )}

            {viewMode === ViewMode.NESTING && (
              <Suspense fallback={
                <div className="w-full h-full flex items-center justify-center bg-slate-950">
                  <div className="text-center text-slate-400">
                    <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                    <p className="text-sm">Loading nesting module...</p>
                  </div>
                </div>
              }>
                <NestingView materialLibrary={MATERIAL_LIBRARY} />
              </Suspense>
            )}
          </ErrorBoundary>
        }
        statusBar={
          <StatusBar
            zoom={zoom}
            onZoomChange={setZoom}
            gridSize={gridSize}
            onGridChange={setGridSize}
            showGrid={showGrid}
            onGridToggle={() => setShowGrid(!showGrid)}
            selectedCount={selectedPanelId ? 1 : 0}
            panelCount={panels.length}
            currentMode={viewMode}
            fps={60}
          />
        }
      />
    </>
  );
};

export default AppModern;
