
import React, { useState, useEffect } from 'react';
import { useProjectStore } from './store/projectStore';
import { Panel, Axis, TextureType, Material, ProjectSnapshot, CabinetConfig, Section } from './types';
import Scene3D from './components/Scene3D';
import EditorPanel from './components/EditorPanel';
import CutList from './components/CutList';
import DrawingView from './components/DrawingView';
import NestingView from './components/NestingView';
import ProductionPipeline from './components/ProductionPipeline';
import { CabinetWizard } from './components/CabinetWizard';
import AIAssistant from './components/AIAssistant';
import ScriptEditor from './components/ScriptEditor';
import ProjectLibrary from './components/ProjectLibrary';
import TemplateSelector from './components/TemplateSelector';
import ToastProvider from './components/ToastProvider';
import ErrorBoundary from './components/ErrorBoundary';
import { HelpPanel } from './components/HelpPanel';
import { OnboardingTour } from './components/OnboardingTour';
import { Tooltip } from './components/Tooltip';
import { AssemblyGuide } from './components/AssemblyGuide';
import { ExportPanel } from './components/ExportPanel';
import { initializeGemini } from './services/geminiService';
import { storageService } from './services/storageService';
import { useAutoSave } from './hooks/useAutoSave';
import { MATERIAL_LIBRARY } from './data/materials';
import { Layout, Box, Scissors, BrainCircuit, PenTool, Undo2, Save, Grid, Factory, Wand2, FileCode, Menu, X, FolderOpen, LayoutDashboard, Clock, AlertTriangle, CheckCircle2, RotateCw, HelpCircle, BookOpen } from 'lucide-react';

enum ViewMode {
  DESIGN = 'design',
  CUT_LIST = 'cut_list',
  DRAWING = 'drawing',
  NESTING = 'nesting',
  PRODUCTION = 'production',
  WIZARD = 'wizard',
  SCRIPT = 'script',
  ASSEMBLY = 'assembly'
}

// Recovery Modal Component
const RecoveryModal: React.FC<{ timestamp: number; onRecover: () => void; onDiscard: () => void }> = ({ timestamp, onRecover, onDiscard }) => (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-in fade-in">
        <div className="bg-[#252526] border border-orange-500/50 rounded-xl p-6 max-w-md w-full shadow-2xl relative">
            <div className="flex items-start gap-4 mb-4">
                <div className="p-3 bg-orange-900/30 rounded-full text-orange-500">
                    <AlertTriangle size={32} />
                </div>
                <div>
                    <h3 className="text-lg font-bold text-white mb-1">Восстановление проекта</h3>
                    <p className="text-sm text-slate-400">
                        Обнаружена несохраненная копия проекта от: <br/>
                        <span className="text-white font-mono">{new Date(timestamp).toLocaleString()}</span>
                    </p>
                </div>
            </div>
            <p className="text-xs text-slate-500 mb-6 bg-black/20 p-3 rounded border border-slate-700">
                Это может произойти из-за сбоя браузера или закрытия вкладки без сохранения. Хотите восстановить данные?
            </p>
            <div className="flex gap-3">
                <button onClick={onDiscard} className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-sm font-bold transition">
                    Удалить
                </button>
                <button onClick={onRecover} className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-bold transition shadow-lg shadow-blue-900/20">
                    Восстановить
                </button>
            </div>
        </div>
    </div>
);

const App: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>(ViewMode.WIZARD);
  const [showAI, setShowAI] = useState(false);
  const [showLibrary, setShowLibrary] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [scriptCode, setScriptCode] = useState('');
  
  // Wizard State to pass down
  const [wizardTemplate, setWizardTemplate] = useState<{config: CabinetConfig, sections: Section[]} | null>(null);

  // Auto-Save Configuration
  const [autoSaveEnabled, setAutoSaveEnabled] = useState(true);
  const [autoSaveInterval, setAutoSaveInterval] = useState(30000); // 30s
  const [showRecovery, setShowRecovery] = useState(false);

  const { panels, setPanels, undo, redo, layers, addToast, selectedPanelId, selectPanel } = useProjectStore();

  // --- AUTO SAVE HOOK ---
  // We save the panels and the wizard configuration to reconstruct state
  const projectStateToSave = { panels, wizardTemplate };
  
  const { saveStatus, lastSaved, recoveryData, clearRecovery, forceSave } = useAutoSave(
      projectStateToSave,
      { enabled: autoSaveEnabled, intervalMs: autoSaveInterval, storageKey: 'bazis_autosave_v1' }
  );

  // Check for recovery on mount
  useEffect(() => {
      if (recoveryData) {
          setShowRecovery(true);
      }
  }, [recoveryData]);

  const handleRecover = () => {
      if (recoveryData && recoveryData.data) {
          if (recoveryData.data.panels) setPanels(recoveryData.data.panels);
          if (recoveryData.data.wizardTemplate) setWizardTemplate(recoveryData.data.wizardTemplate);
          addToast('Проект восстановлен', 'success');
          // Don't clear immediately, wait for next save cycle to overwrite
      }
      setShowRecovery(false);
  };

  const handleDiscardRecovery = () => {
      clearRecovery();
      setShowRecovery(false);
      addToast('Черновик удален', 'info');
  };

  // --- INITIALIZATION ---
  useEffect(() => {
    // Initialize AI Service
    if (process.env.API_KEY) {
      initializeGemini(process.env.API_KEY);
    }

    // Default Load if no recovery needed (simple check)
    // Note: useAutoSave handles the logic of finding data. 
    // We only load default if panels are empty AND no recovery happened.
    if (panels.length === 0 && !recoveryData) {
        loadDefaultProject();
    }
  }, [recoveryData]); // Re-evaluate if recoveryData becomes available late (though it's usually instant from LS)

  const loadDefaultProject = () => {
      // Dimensions: 1800W x 2500H x 650D
      const initialPanels: Panel[] = [
        { 
          id: '1', name: 'Боковина левая', width: 650, height: 2500, depth: 16, x: 0, y: 0, z: 0, rotation: Axis.X, materialId: 'eg-w980', color: '#FFFFFF', 
          texture: TextureType.UNIFORM, textureRotation: 0, visible: true, layer: 'body', openingType: 'none', edging: {top: 'none', bottom: '0.4', left: 'none', right: '2.0'}, groove: {enabled: false, side: 'top', width: 4, depth: 10, offset: 20}, hardware: []
        },
        { 
          id: '2', name: 'Боковина правая', width: 650, height: 2500, depth: 16, x: 1784, y: 0, z: 0, rotation: Axis.X, materialId: 'eg-w980', color: '#FFFFFF', 
          texture: TextureType.UNIFORM, textureRotation: 0, visible: true, layer: 'body', openingType: 'none', edging: {top: 'none', bottom: '0.4', left: 'none', right: '2.0'}, groove: {enabled: false, side: 'top', width: 4, depth: 10, offset: 20}, hardware: []
        },
        { 
          id: '3', name: 'Крышка', width: 1800, height: 650, depth: 16, x: 0, y: 2484, z: 0, rotation: Axis.Y, materialId: 'eg-w980', color: '#FFFFFF', 
          texture: TextureType.UNIFORM, textureRotation: 0, visible: true, layer: 'body', openingType: 'none', edging: {top: '2.0', bottom: 'none', left: '2.0', right: '2.0'}, groove: {enabled: false, side: 'top', width: 4, depth: 10, offset: 20}, hardware: []
        }
    ];
    setPanels(initialPanels);
  };

  // --- KEYBOARD SHORTCUTS ---
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        undo();
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        redo();
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
          e.preventDefault();
          handleSaveProject();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo, panels]);

  const handleSaveProject = async () => {
      const name = prompt("Введите имя проекта:", `Проект ${new Date().toLocaleDateString()}`);
      if (!name) return;

      const project: ProjectSnapshot = {
          id: `proj-${Date.now()}`,
          name: name,
          timestamp: Date.now(),
          version: 1,
          panels: panels,
          layers: layers,
          config: wizardTemplate?.config, // Save wizard config if available
      };

      try {
          await storageService.saveProject(project);
          // Saving manually clears the temporary recovery data as it is now "safe"
          clearRecovery(); 
          addToast('Проект сохранен в библиотеку', 'success');
      } catch (e) {
          console.error(e);
          addToast('Ошибка сохранения', 'error');
      }
  };

  const handleLoadProject = (project: ProjectSnapshot) => {
      setPanels(project.panels);
      if (project.config) {
          // Reconstruct wizard state roughly
          setWizardTemplate({ config: project.config, sections: [] });
      }
      addToast(`Загружен проект: ${project.name}`, 'success');
      setShowLibrary(false);
      setViewMode(ViewMode.DESIGN);
  };

  const handleApplyTemplate = (template: { config: CabinetConfig, sections: Section[] }) => {
      setWizardTemplate(template);
      setShowTemplates(false);
      setViewMode(ViewMode.WIZARD);
      addToast('Шаблон применен в Мастере', 'success');
  };

  // --- SCRIPT EXECUTION ENGINE ---
  const handleRunScript = (code: string) => {
      try {
          const newPanels: Panel[] = [];
          let idCounter = 1;

          // Define DSL Environment
          const DeleteAll = () => { newPanels.length = 0; };
          const AddPanel = (w: number, h: number, th: number = 16) => {
              const p: Panel = {
                  id: `scr-${Date.now()}-${idCounter++}`,
                  name: 'Panel',
                  width: w, height: h, depth: th,
                  x: 0, y: 0, z: 0, rotation: Axis.Y,
                  materialId: 'eg-w980', color: '#FFFFFF', texture: TextureType.UNIFORM, textureRotation: 0,
                  visible: true, layer: 'body', openingType: 'none',
                  edging: {top:'none',bottom:'none',left:'none',right:'none'},
                  groove: {enabled:false, side:'top', width:0, depth:0, offset:0},
                  hardware: []
              };
              newPanels.push(p);

              // Builder Pattern for Script
              return {
                  setName: function(n: string) { p.name = n; return this; },
                  setOrient: function(axis: string) { p.rotation = axis as Axis; return this; },
                  setColor: function(c: string) { p.color = c; return this; },
                  setPos: function(x:number, y:number, z:number) { p.x=x; p.y=y; p.z=z; return this; },
                  setOpening: function(o: string) { p.openingType = o as any; return this; },
                  addEdging: function(...sides: string[]) {
                      sides.forEach(s => { 
                          const parts = s.split(':');
                          const side = parts[0];
                          const val = parts.length > 1 ? parts[1] : '2.0'; 
                          if(side in p.edging) (p.edging as any)[side] = val; 
                      });
                      return this;
                  },
                  setMaterial: function(m: string) {
                      const mat = MATERIAL_LIBRARY.find(lib => lib.id === m);
                      if (mat) {
                          p.materialId = mat.id;
                          p.depth = mat.thickness;
                          p.texture = mat.texture;
                          p.color = mat.color;
                      } else if(m==='ХДФ' || m==='HDF') { 
                          p.materialId='eg-hdf'; p.depth=4; p.texture=TextureType.NONE; 
                      } else if(m==='MDF' || m==='RAL') { 
                          p.materialId='mdf-ral-white'; p.depth=18; p.texture=TextureType.UNIFORM; 
                      } else {
                          p.materialId = m;
                      }
                      return this;
                  },
                  addHardware: function(type: string, x: number, y: number, diameter: number = 5) {
                      const validTypes = ['screw', 'minifix_cam', 'minifix_pin', 'dowel', 'dowel_hole', 'handle', 'hinge_cup', 'shelf_support', 'slide_rail', 'rod_holder', 'pantograph', 'basket_rail', 'legs'];
                      const hwType = validTypes.includes(type) ? type : 'screw';
                      p.hardware.push({
                          id: `hw-${Date.now()}-${Math.random()}`,
                          type: hwType as any,
                          name: type,
                          x, y, diameter
                      });
                      return this;
                  },
                  addGroove: function(width: number, depth: number, offset: number, side: string = 'top') {
                      p.groove = { enabled: true, width, depth, offset, side: side as any };
                      return this;
                  }
              };
          };

          // Safe-ish Evaluation
          // eslint-disable-next-line no-new-func
          const execute = new Function('AddPanel', 'DeleteAll', 'alert', code);
          execute(AddPanel, DeleteAll, (msg: string) => addToast(msg, 'info'));

          setPanels(newPanels);
          setViewMode(ViewMode.DESIGN);
          addToast('Скрипт выполнен успешно', 'success');

      } catch (e: any) {
          console.error(e);
          addToast(`Ошибка выполнения скрипта: ${e.message}`, 'error');
      }
  };

  // Nav Items configuration
  const navItems = [
      { id: ViewMode.DESIGN, label: 'КОНСТРУКТОР', icon: Box },
      { id: ViewMode.WIZARD, label: 'МАСТЕР', icon: Wand2 },
      { id: ViewMode.SCRIPT, label: 'СКРИПТЫ', icon: FileCode },
      { id: ViewMode.DRAWING, label: 'ЧЕРТЕЖИ', icon: PenTool },
      { id: ViewMode.ASSEMBLY, label: 'СБОРКА', icon: BookOpen }, 
      { id: ViewMode.NESTING, label: 'РАСКРОЙ', icon: Grid },
      { id: ViewMode.CUT_LIST, label: 'СМЕТА', icon: Scissors },
      { id: ViewMode.PRODUCTION, label: 'ЦЕХ', icon: Factory },
  ];

  const formatLastSaved = (date: Date | null) => {
      if (!date) return '';
      const diff = Math.floor((Date.now() - date.getTime()) / 1000);
      if (diff < 60) return 'Только что';
      if (diff < 3600) return `${Math.floor(diff/60)} мин. назад`;
      return date.toLocaleTimeString();
  };

  return (
    <div className="h-full w-full flex flex-col bg-[#111] text-slate-300 font-sans overflow-hidden fixed inset-0">
      <ToastProvider />
      <OnboardingTour />
      
      {showRecovery && recoveryData && (
          <RecoveryModal 
              timestamp={recoveryData.timestamp} 
              onRecover={handleRecover} 
              onDiscard={handleDiscardRecovery} 
          />
      )}

      {showLibrary && <ProjectLibrary onLoad={handleLoadProject} onClose={() => setShowLibrary(false)} />}
      {showTemplates && <TemplateSelector onSelect={handleApplyTemplate} onClose={() => setShowTemplates(false)} />}
      {showHelp && <HelpPanel onClose={() => setShowHelp(false)} />}

      {/* HEADER */}
      <header className="bg-[#222] border-b border-slate-700 h-14 flex items-center justify-between px-3 z-30 shrink-0 gap-2">
        <div className="flex items-center gap-2 md:gap-4 shrink-0">
          <div className="flex items-center gap-2">
            <Layout className="text-blue-500" size={24}/>
            <h1 className="font-bold text-sm tracking-wide uppercase text-slate-100 hidden lg:block">Bazis<span className="text-blue-500">Pro</span> Web</h1>
          </div>
          <div className="h-6 w-px bg-slate-700 hidden md:block"></div>
          
          <div className="flex items-center gap-1">
             <Tooltip content="Отменить (Ctrl+Z)">
                <button onClick={undo} className="p-2 hover:bg-slate-700 rounded text-slate-400 hover:text-white" title="Отменить"><Undo2 size={18} /></button>
             </Tooltip>
             <Tooltip content="Сохранить (Ctrl+S)">
                <button onClick={handleSaveProject} className="p-2 hover:bg-slate-700 rounded text-slate-400 hover:text-white" title="Сохранить в библиотеку"><Save size={18} /></button>
             </Tooltip>
             <Tooltip content="Открыть проекты">
                <button onClick={() => setShowLibrary(true)} className="p-2 hover:bg-slate-700 rounded text-slate-400 hover:text-white" title="Мои Проекты"><FolderOpen size={18} /></button>
             </Tooltip>
             <Tooltip content="Шаблоны мебели">
                <button onClick={() => setShowTemplates(true)} className="p-2 hover:bg-slate-700 rounded text-slate-400 hover:text-white" title="Шаблоны"><LayoutDashboard size={18} /></button>
             </Tooltip>
          </div>
        </div>
        
        {/* SCROLLABLE NAVIGATION */}
        <div className="flex-1 overflow-x-auto no-scrollbar mx-2 mask-linear-fade">
            <div className="flex items-center bg-[#333] rounded p-0.5 gap-0.5 border border-slate-700 shadow-inner w-max">
            {navItems.map(item => (
                <button 
                    key={item.id}
                    onClick={() => setViewMode(item.id)} 
                    className={`px-3 py-1.5 rounded flex items-center gap-2 text-xs font-bold transition whitespace-nowrap 
                    ${viewMode === item.id ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:text-white hover:bg-slate-700'}`}
                >
                    <item.icon size={14} /> 
                    <span className="hidden md:inline">{item.label}</span>
                </button>
            ))}
            </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
            {/* Auto-Save Indicator */}
            {autoSaveEnabled && (
                <div 
                    className={`hidden md:flex items-center gap-2 px-3 py-1.5 rounded border text-[10px] font-bold transition-all cursor-pointer
                    ${saveStatus === 'saved' ? 'border-emerald-500/30 text-emerald-400 bg-emerald-900/10' : 'border-orange-500/30 text-orange-400 bg-orange-900/10'}`}
                    onClick={forceSave}
                    title={saveStatus === 'unsaved' ? 'Есть несохраненные изменения' : 'Все сохранено'}
                >
                    {saveStatus === 'saving' ? (
                        <RotateCw size={12} className="animate-spin" />
                    ) : saveStatus === 'saved' ? (
                        <CheckCircle2 size={12} />
                    ) : (
                        <AlertTriangle size={12} />
                    )}
                    <span className="whitespace-nowrap">
                        {saveStatus === 'saved' ? `Сохранено ${formatLastSaved(lastSaved)}` : saveStatus === 'saving' ? 'Сохранение...' : 'Не сохранено'}
                    </span>
                </div>
            )}

            <button 
                onClick={() => setShowHelp(true)}
                className="flex items-center gap-2 px-3 py-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition"
                title="Справка"
            >
                <HelpCircle size={18}/>
            </button>

            <button 
                onClick={() => setShowAI(!showAI)} 
                className={`flex items-center gap-2 px-3 py-1.5 rounded border border-indigo-500/50 text-xs font-bold hover:bg-indigo-900 transition ${showAI ? 'bg-indigo-700 text-white' : 'text-indigo-400'}`}
            >
            <BrainCircuit size={18} /> <span className="hidden sm:inline">AI</span>
            </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden relative">
        
        {/* LEFT/RIGHT PANELS HANDLING FOR MOBILE */}
        {showAI && (
            <div className="absolute inset-0 md:relative md:w-80 md:inset-auto z-40 bg-slate-50 md:bg-transparent shadow-xl md:shadow-none transition-all flex flex-col">
                <div className="md:hidden flex justify-between items-center p-3 bg-white border-b border-slate-200">
                    <span className="font-bold text-slate-800">ИИ Ассистент</span>
                    <button onClick={() => setShowAI(false)} className="p-2 bg-slate-100 rounded-full shadow hover:bg-slate-200"><X size={20} className="text-slate-700"/></button>
                </div>
                <div className="flex-1 overflow-hidden">
                    <AIAssistant 
                        materialLibrary={MATERIAL_LIBRARY} 
                        onApplyTemplate={handleApplyTemplate} 
                    />
                </div>
            </div>
        )}

        <main className="flex-1 relative bg-[#0f0f0f] overflow-hidden flex flex-col w-full">
            {/* Global Export Panel - Available in relevant modes */}
            {viewMode === ViewMode.DESIGN && <ExportPanel />}

            {viewMode === ViewMode.DESIGN && (
                <ErrorBoundary componentName="3D Сцена">
                    <Scene3D />
                </ErrorBoundary>
            )}
            {viewMode === ViewMode.WIZARD && (
                <ErrorBoundary componentName="Мастер Шкафа">
                    <CabinetWizard 
                        materialLibrary={MATERIAL_LIBRARY} 
                        onGenerate={(p) => { setPanels(p); setViewMode(ViewMode.DESIGN); }} 
                        initialState={wizardTemplate}
                    />
                </ErrorBoundary>
            )}
            {viewMode === ViewMode.SCRIPT && (
                <ErrorBoundary componentName="Редактор Скриптов">
                    <ScriptEditor code={scriptCode} onChange={setScriptCode} onRun={handleRunScript} />
                </ErrorBoundary>
            )}
            {viewMode === ViewMode.DRAWING && (
                <ErrorBoundary componentName="Чертежи">
                    <DrawingView onClose={() => setViewMode(ViewMode.DESIGN)} />
                </ErrorBoundary>
            )}
            {viewMode === ViewMode.NESTING && (
                <ErrorBoundary componentName="Раскрой">
                    <NestingView materialLibrary={MATERIAL_LIBRARY} />
                </ErrorBoundary>
            )}
            {viewMode === ViewMode.PRODUCTION && (
                <ErrorBoundary componentName="MES Система">
                    <ProductionPipeline materialLibrary={MATERIAL_LIBRARY} />
                </ErrorBoundary>
            )}
            {viewMode === ViewMode.CUT_LIST && (
                <ErrorBoundary componentName="Смета">
                    <CutList materialLibrary={MATERIAL_LIBRARY} />
                </ErrorBoundary>
            )}
            {viewMode === ViewMode.ASSEMBLY && (
                <ErrorBoundary componentName="Инструкция по сборке">
                    <AssemblyGuide onClose={() => setViewMode(ViewMode.DESIGN)} />
                </ErrorBoundary>
            )}
        </main>

        {/* EDITOR PANEL / STRUCTURE TREE */}
        {(viewMode === ViewMode.DESIGN || viewMode === ViewMode.DRAWING) && (
          <div className={`
            absolute inset-x-0 bottom-0 h-[60vh] md:h-full md:top-0 md:relative md:w-80 md:inset-auto z-30 shadow-2xl md:shadow-none border-t md:border-t-0 md:border-l border-slate-700 bg-[#1e1e1e] flex flex-col transition-transform
            ${!selectedPanelId && window.innerWidth < 768 ? 'translate-y-full md:translate-y-0' : 'translate-y-0'}
          `}>
              <div className="md:hidden flex justify-between items-center p-2 bg-[#252526] border-b border-slate-700">
                  <span className="text-xs text-slate-400 uppercase font-bold pl-2">{selectedPanelId ? 'Свойства детали' : 'Структура проекта'}</span>
                  <button onClick={() => selectPanel(null)} className="p-1.5 bg-slate-700 text-white rounded shadow flex items-center gap-1 text-xs">
                      <X size={14}/>
                  </button>
              </div>
              <div className="flex-1 overflow-hidden">
                <ErrorBoundary componentName="Редактор Свойств">
                    <EditorPanel 
                        materialLibrary={MATERIAL_LIBRARY} 
                        isDrawingMode={viewMode === ViewMode.DRAWING}
                        onToggleView={() => setViewMode(viewMode === ViewMode.DRAWING ? ViewMode.DESIGN : ViewMode.DRAWING)}
                    />
                </ErrorBoundary>
              </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default App;
