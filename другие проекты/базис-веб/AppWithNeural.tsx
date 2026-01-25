import React, { useState, useEffect, Suspense } from 'react';
import { useProjectStore } from './store/projectStore';
import { Panel, Axis, TextureType } from './types';
import { MATERIAL_LIBRARY } from './materials.config';
import { DEFAULT_CABINET_CONFIG } from './constants';

// UI Components
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
const Scene3DSimple = React.lazy(() => import('./components/Scene3DSimple'));
const Scene3DBabylon = React.lazy(() => import('./components/Scene3DBabylon'));
const NestingView = React.lazy(() => import('./components/NestingView'));
const DrawingTab = React.lazy(() => import('./components/DrawingTab'));
const NeuralGenerationPanel = React.lazy(() => import('./components/NeuralGenerationPanel'));

// Static Views
import { CabinetWizard } from './components/CabinetWizard';
import ParametricEditor from './components/ParametricEditor';
import ToastProvider from './components/ToastProvider';
import ErrorBoundary from './components/ErrorBoundary';
import { initializeGemini } from './services/geminiService';

enum ViewMode {
  DESIGN = 'design',
  WIZARD = 'wizard',
  CUT_LIST = 'cut_list',
  DRAWING = 'drawing',
  NESTING = 'nesting',
  PRODUCTION = 'production',
  NEURAL = 'neural',
}

const App: React.FC = () => {
  // State
  const [viewMode, setViewMode] = useState<ViewMode>(ViewMode.WIZARD);
  const [zoom, setZoom] = useState(100);
  const [gridSize, setGridSize] = useState(50);
  const [showGrid, setShowGrid] = useState(true);
  const [projectName, setProjectName] = useState('Мой проект');
  const [isDirty, setIsDirty] = useState(false);
  const [showFileDialog, setShowFileDialog] = useState(false);
  const [showSettingsDialog, setShowSettingsDialog] = useState(false);
  const [show3DView, setShow3DView] = useState(true);
  const [engine3D, setEngine3D] = useState<'three' | 'babylon' | 'simple'>('simple');

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

    // Load last project
    const saved = localStorage.getItem('bazis_project_current');
    if (saved) {
      try {
        const data = JSON.parse(saved);
        if (data.panels && data.panels.length > 0) {
          setPanels(data.panels);
          setProjectName(data.projectName);
          setViewMode(ViewMode.DESIGN);
        }
      } catch (e) {
        console.error('Failed to load saved project:', e);
      }
    }

    // Listen for neural generation events
    const handleNeuralGeneration = (event: CustomEvent) => {
      const { geometry, parameters } = event.detail;
      addToast(`✨ Neural generation: ${geometry.metrics.vertexCount} vertices`, 'success');
    };

    window.addEventListener('neural-cabinet-generated', handleNeuralGeneration as EventListener);
    return () => {
      window.removeEventListener('neural-cabinet-generated', handleNeuralGeneration as EventListener);
    };
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
    const timestamp = new Date().toLocaleString();
    localStorage.setItem(`bazis_project_${projectName}_${timestamp}`, JSON.stringify({ panels, projectName }));
    setIsDirty(false);
    addToast(`✓ Сохранено: ${projectName}`, 'success');
  };

  const handleLoad = () => {
    setShowFileDialog(true);
  };

  // Keyboard shortcuts
  useEffect(() => {
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
      } else if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        // Ctrl+N for Neural generation view
        e.preventDefault();
        setViewMode(ViewMode.NEURAL);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedPanelId, undo, redo]);

  const selectedPanel = panels.find((p) => p.id === selectedPanelId) || null;

  return (
    <>
      <ToastProvider />

      {/* File Dialog */}
      <FileDialog
        isOpen={showFileDialog}
        onClose={() => setShowFileDialog(false)}
        onSave={handleSave}
        recentFiles={['Шкаф простой', 'Модульная система', 'Кухонный гарнитур']}
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
            menuOpen={false}
            onMenuToggle={() => {}}
            onSave={handleSave}
            onLoad={handleLoad}
            onSettings={() => setShowSettingsDialog(true)}
            isDirty={isDirty}
          />
        }
        toolbar={
          <Toolbar
            onUndo={undo}
            onRedo={redo}
            onDelete={() => selectedPanelId && deletePanel(selectedPanelId)}
            onCopy={() => addToast('Копирование', 'info')}
            onPaste={() => addToast('Вставка', 'info')}
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
          <div className="flex flex-col gap-2 pb-4">
            {/* View Mode Switcher */}
            <div className="px-4 py-2 border-b border-slate-700">
              <div className="text-xs font-semibold text-slate-400 mb-2">VIEW MODE</div>
              <div className="space-y-1">
                <button
                  onClick={() => setViewMode(ViewMode.WIZARD)}
                  className={`w-full px-3 py-1 rounded text-xs font-medium transition ${
                    viewMode === ViewMode.WIZARD
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  📋 Wizard
                </button>
                <button
                  onClick={() => setViewMode(ViewMode.DESIGN)}
                  className={`w-full px-3 py-1 rounded text-xs font-medium transition ${
                    viewMode === ViewMode.DESIGN
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  ✏️ Design
                </button>
                <button
                  onClick={() => setViewMode(ViewMode.NEURAL)}
                  className={`w-full px-3 py-1 rounded text-xs font-medium transition ${
                    viewMode === ViewMode.NEURAL
                      ? 'bg-cyan-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                  title="Ctrl+N"
                >
                  ✨ Neural Gen
                </button>
              </div>
            </div>

            {/* Layers */}
            {viewMode !== ViewMode.NEURAL && (
              <SidePanel
                layers={layers}
                panels={panels}
                selectedPanelId={selectedPanelId}
                onSelectPanel={selectPanel}
                onToggleLayerVisibility={() => {}}
                onToggleLayerLocked={() => {}}
                onDeletePanel={deletePanel}
                onRenamePanel={(id, name) => updatePanel(id, { name })}
              />
            )}
          </div>
        }
        rightPanel={
          viewMode === ViewMode.NEURAL ? (
            <Suspense
              fallback={
                <div className="w-full h-full flex items-center justify-center bg-slate-950">
                  <div className="text-center text-slate-400">
                    <div className="w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                    <p className="text-sm">Loading Neural Generator...</p>
                  </div>
                </div>
              }
            >
              <NeuralGenerationPanel />
            </Suspense>
          ) : (
            <PropertiesPanel
              selectedPanel={selectedPanel}
              onPanelUpdate={(id, changes) => updatePanel(id, changes)}
              materials={MATERIAL_LIBRARY}
            />
          )
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
                    <Suspense
                      fallback={
                        <div className="w-full h-full flex items-center justify-center bg-slate-950">
                          <div className="text-center text-slate-400">
                            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                            <p className="text-sm">Loading 3D engine...</p>
                          </div>
                        </div>
                      }
                    >
                      {engine3D === 'babylon' ? (
                        <Scene3DBabylon />
                      ) : engine3D === 'three' ? (
                        <Scene3D />
                      ) : (
                        <Scene3DSimple />
                      )}
                    </Suspense>
                  )}

                  <div className="absolute top-20 left-4 z-50 bg-black/90 p-3 rounded-lg border border-gray-600 shadow-xl">
                    <div className="flex gap-2">
                      <button
                        onClick={() => setEngine3D('simple')}
                        className={`px-3 py-2 text-xs rounded-lg font-semibold ${
                          engine3D === 'simple'
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-700 text-gray-300'
                        }`}
                      >
                        Simple
                      </button>
                      <button
                        onClick={() => setEngine3D('three')}
                        className={`px-3 py-2 text-xs rounded-lg font-semibold ${
                          engine3D === 'three'
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-700 text-gray-300'
                        }`}
                      >
                        Three.js
                      </button>
                      <button
                        onClick={() => setEngine3D('babylon')}
                        className={`px-3 py-2 text-xs rounded-lg font-semibold ${
                          engine3D === 'babylon'
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-700 text-gray-300'
                        }`}
                      >
                        Babylon.js
                      </button>
                    </div>
                  </div>
                </div>

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

                <div className="w-80 shrink-0 overflow-hidden border-l border-slate-700">
                  <ParametricEditor selectedPanel={selectedPanel} />
                </div>
              </div>
            )}

            {viewMode === ViewMode.NEURAL && (
              <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-950 to-slate-900 p-8">
                <Suspense
                  fallback={
                    <div className="text-center text-slate-400">
                      <div className="w-12 h-12 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                      <p className="text-sm">Loading Neural Generator...</p>
                    </div>
                  }
                >
                  <NeuralGenerationPanel />
                </Suspense>
              </div>
            )}

            {viewMode === ViewMode.NESTING && (
              <Suspense
                fallback={
                  <div className="w-full h-full flex items-center justify-center bg-slate-950">
                    <div className="text-center text-slate-400">
                      <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                      <p className="text-sm">Loading nesting module...</p>
                    </div>
                  </div>
                }
              >
                <NestingView materialLibrary={MATERIAL_LIBRARY} />
              </Suspense>
            )}

            {viewMode === ViewMode.DRAWING && (
              <Suspense
                fallback={
                  <div className="w-full h-full flex items-center justify-center bg-slate-950">
                    <div className="text-center text-slate-400">
                      <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                      <p className="text-sm">Loading drawing module...</p>
                    </div>
                  </div>
                }
              >
                <DrawingTab />
              </Suspense>
            )}

            {viewMode !== ViewMode.DESIGN &&
              viewMode !== ViewMode.WIZARD &&
              viewMode !== ViewMode.NESTING &&
              viewMode !== ViewMode.DRAWING &&
              viewMode !== ViewMode.NEURAL && (
                <div className="w-full h-full flex items-center justify-center bg-slate-950">
                  <div className="text-center text-slate-400">
                    <h2 className="text-xl font-bold mb-2">Coming soon</h2>
                    <p className="text-sm">{viewMode} mode</p>
                  </div>
                </div>
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

export default App;
