
import React, { useState, useMemo } from 'react';
import { useProjectStore } from '../store/projectStore';
import PanelDrawing from './PanelDrawing';
import { AssemblyGuide } from './AssemblyGuide';
import { PenTool, Printer, FileDown, Box, GalleryVerticalEnd, LayoutTemplate, Eye, EyeOff, Wrench } from 'lucide-react';
import { DxfExporter } from '../services/DxfExporter';
import { TechnicalDrawing, ViewType } from '../services/TechnicalDrawing';
import { Panel } from '../types';
import { Tooltip } from './Tooltip';

interface DrawingViewProps {
    onClose?: () => void;
}

// Sub-component for individual sheet (Album mode)
const DrawingSheet: React.FC<{ panel: Panel; index: number; total: number }> = ({ panel, index, total }) => {
    const hardware = panel.hardware || [];
    
    return (
        <div className="bg-white shadow-lg border border-slate-300 mb-8 break-inside-avoid print:mb-0 print:break-after-page print:border-none print:shadow-none w-full max-w-[210mm] aspect-[210/297] mx-auto print:w-full print:h-screen flex flex-col p-8 md:p-12 relative">
            {/* Title Block */}
            <div className="border-b-2 border-black pb-4 mb-6 flex justify-between items-end">
                <div>
                    <div className="text-xs text-slate-500 uppercase font-bold mb-1">Деталь №{index + 1}</div>
                    <h1 className="text-2xl font-bold text-black leading-none">{panel.name}</h1>
                    <div className="text-xs font-mono mt-2 text-slate-600">ID: {panel.id.slice(-8)} | {panel.materialId}</div>
                </div>
                <div className="text-right">
                    <div className="text-3xl font-black tracking-tighter">{panel.width} <span className="text-slate-400">x</span> {panel.height}</div>
                    <div className="text-xs font-bold mt-1 bg-black text-white inline-block px-2 py-0.5">S = {panel.depth}мм</div>
                </div>
            </div>

            {/* Drawing Area */}
            <div className="flex-1 border border-slate-200 relative mb-6 min-h-[300px]">
                <PanelDrawing panel={panel} width={800} height={600} detailed={true} />
                <div className="absolute bottom-2 left-2 flex flex-col text-[10px] text-slate-400 font-mono">
                    <span>FACE SIDE</span>
                    <span>SCALE: NTS</span>
                </div>
            </div>

            {/* Footer Spec */}
            <div className="mt-auto grid grid-cols-2 gap-8 text-xs">
                <div>
                    <h3 className="font-bold uppercase border-b border-black mb-2">Кромка</h3>
                    <div className="grid grid-cols-2 gap-y-1">
                        <div>Верх: <b>{panel.edging.top !== 'none' ? panel.edging.top : '-'}</b></div>
                        <div>Низ: <b>{panel.edging.bottom !== 'none' ? panel.edging.bottom : '-'}</b></div>
                        <div>Лев: <b>{panel.edging.left !== 'none' ? panel.edging.left : '-'}</b></div>
                        <div>Прав: <b>{panel.edging.right !== 'none' ? panel.edging.right : '-'}</b></div>
                    </div>
                </div>
                <div>
                    <h3 className="font-bold uppercase border-b border-black mb-2">Инфо</h3>
                    <div>Отв: {hardware.length}</div>
                    <div>Паз: {panel.groove?.enabled ? 'ДА' : 'НЕТ'}</div>
                </div>
            </div>
            
            <div className="absolute bottom-4 right-8 text-[10px] text-slate-400 print:text-black">
                Лист {index + 1} из {total} | BazisPro Web
            </div>
        </div>
    );
};

// Sub-component for Technical Views (Front/Top/Side)
const TechnicalViewCanvas: React.FC<{ panels: Panel[], view: ViewType }> = ({ panels, view }) => {
    const [showDims, setShowDims] = useState(true);
    const [showHidden, setShowHidden] = useState(false);

    const svgContent = useMemo(() => {
        const entities = TechnicalDrawing.generateView(panels, view);
        // Filter layers
        const filtered = entities.filter(e => {
            if (!showDims && e.layer === 'dimension') return false;
            if (!showHidden && e.layer === 'hidden') return false;
            return true;
        });
        return TechnicalDrawing.exportSVG(filtered);
    }, [panels, view, showDims, showHidden]);

    const handleDownloadSVG = () => {
        const blob = new Blob([svgContent], { type: 'image/svg+xml' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `view_${view}.svg`;
        link.click();
    };

    return (
        <div className="flex flex-col h-full bg-white relative">
            {/* View Controls */}
            <div className="absolute top-4 right-4 flex flex-col gap-2 bg-white/90 p-2 rounded shadow border border-slate-200 z-10 print:hidden">
                <button onClick={() => setShowDims(!showDims)} className={`p-2 rounded text-xs font-bold flex items-center gap-2 ${showDims ? 'bg-blue-100 text-blue-700' : 'text-slate-500 hover:bg-slate-100'}`}>
                    {showDims ? <Eye size={14}/> : <EyeOff size={14}/>} Размеры
                </button>
                <button onClick={() => setShowHidden(!showHidden)} className={`p-2 rounded text-xs font-bold flex items-center gap-2 ${showHidden ? 'bg-blue-100 text-blue-700' : 'text-slate-500 hover:bg-slate-100'}`}>
                    {showHidden ? <Eye size={14}/> : <EyeOff size={14}/>} Невидимые
                </button>
                <hr className="border-slate-200"/>
                <button onClick={handleDownloadSVG} className="p-2 rounded hover:bg-slate-100 text-xs text-slate-600 flex items-center gap-2">
                    <FileDown size={14}/> Скачать SVG
                </button>
            </div>

            {/* Canvas */}
            <div className="flex-1 p-8 flex items-center justify-center overflow-auto bg-[radial-gradient(#e5e7eb_1px,transparent_1px)] [background-size:20px_20px]">
                <div 
                    className="w-full h-full max-w-4xl max-h-[80vh] shadow-2xl bg-white border border-slate-800"
                    dangerouslySetInnerHTML={{ __html: svgContent }} 
                />
            </div>
            
            <div className="absolute bottom-4 left-4 bg-black text-white px-3 py-1 text-xs font-mono rounded opacity-50 pointer-events-none uppercase">
                PROJECTION: {view}
            </div>
        </div>
    );
};

export default function DrawingView({ onClose }: DrawingViewProps) {
  const { panels, selectedPanelId } = useProjectStore();
  
  // Modes: 'view_front', 'view_top', 'view_side', 'detail', 'all', 'assembly'
  const [mode, setMode] = useState<string>('view_front');

  const selectedPanel = panels.find(p => p.id === selectedPanelId);
  const visiblePanels = panels.filter(p => p.visible);

  const handleDxfExport = () => {
      const dxfContent = DxfExporter.export(panels);
      const blob = new Blob([dxfContent], { type: 'application/dxf' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `project_${Date.now()}.dxf`;
      link.click();
  };

  // --- TOOLBAR ---
  const renderToolbar = () => (
      <div className="bg-slate-200 p-2 flex flex-wrap gap-2 border-b border-slate-300 print:hidden shrink-0 items-center shadow-sm z-20 relative">
           {onClose && (
               <button onClick={onClose} className="px-3 py-2 rounded bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold flex items-center gap-2 shadow-sm">
                   <Box size={16}/> <span className="hidden sm:inline">3D Сцена</span>
               </button>
           )}
           <div className="h-6 w-px bg-slate-300 mx-1 hidden sm:block"></div>
           
           {/* Technical Views */}
           <div className="flex bg-slate-300 rounded p-0.5 gap-0.5">
               <button onClick={() => setMode('view_front')} className={`px-3 py-1.5 rounded text-xs font-bold transition ${mode === 'view_front' ? 'bg-white shadow text-blue-700' : 'text-slate-600 hover:text-black'}`}>Фронт</button>
               <button onClick={() => setMode('view_side')} className={`px-3 py-1.5 rounded text-xs font-bold transition ${mode === 'view_side' ? 'bg-white shadow text-blue-700' : 'text-slate-600 hover:text-black'}`}>Сбоку</button>
               <button onClick={() => setMode('view_top')} className={`px-3 py-1.5 rounded text-xs font-bold transition ${mode === 'view_top' ? 'bg-white shadow text-blue-700' : 'text-slate-600 hover:text-black'}`}>Сверху</button>
           </div>

           <div className="h-6 w-px bg-slate-300 mx-1 hidden sm:block"></div>

           {/* Detail Views */}
           <button onClick={() => setMode('detail')} className={`px-3 py-2 rounded text-xs font-bold flex items-center gap-2 transition ${mode === 'detail' ? 'bg-blue-600 text-white shadow' : 'bg-slate-300 text-slate-700 hover:bg-white'}`}>
                <LayoutTemplate size={16}/> <span className="hidden sm:inline">Деталь</span>
           </button>
           <button onClick={() => setMode('all')} className={`px-3 py-2 rounded text-xs font-bold flex items-center gap-2 transition ${mode === 'all' ? 'bg-blue-600 text-white shadow' : 'bg-slate-300 text-slate-700 hover:bg-white'}`}>
                <GalleryVerticalEnd size={16}/> <span className="hidden sm:inline">Альбом</span>
           </button>

           <div className="h-6 w-px bg-slate-300 mx-1 hidden sm:block"></div>

           {/* Assembly Integration */}
           <button onClick={() => setMode('assembly')} className={`px-3 py-2 rounded text-xs font-bold flex items-center gap-2 transition ${mode === 'assembly' ? 'bg-indigo-600 text-white shadow' : 'bg-slate-300 text-slate-700 hover:bg-white'}`}>
                <Wrench size={16}/> <span className="hidden sm:inline">Сборка</span>
           </button>
           
           <div className="flex-1"></div>
           
           <Tooltip content="Скачать файл для ЧПУ-станка (.dxf)">
               <button onClick={handleDxfExport} className="px-3 py-2 rounded bg-emerald-600 text-white text-xs font-bold flex items-center gap-2 hover:bg-emerald-700 shadow-sm">
                   <FileDown size={16}/> <span className="hidden sm:inline">DXF</span>
               </button>
           </Tooltip>
           <Tooltip content="Печать чертежей (Ctrl+P)">
               <button onClick={() => window.print()} className="px-3 py-2 rounded bg-slate-800 text-white text-xs font-bold flex items-center gap-2 hover:bg-slate-700 shadow-sm">
                   <Printer size={16}/> <span className="hidden sm:inline">Печать</span>
               </button>
           </Tooltip>
      </div>
  );
  
  // --- RENDER CONTENT ---
  return (
      <div className="h-full flex flex-col bg-slate-100 overflow-hidden">
          {renderToolbar()}
          
          <div className="flex-1 relative overflow-hidden bg-slate-50">
              {mode === 'view_front' && <TechnicalViewCanvas panels={visiblePanels} view="front" />}
              {mode === 'view_top' && <TechnicalViewCanvas panels={visiblePanels} view="top" />}
              {mode === 'view_side' && <TechnicalViewCanvas panels={visiblePanels} view="left" />}
              
              {mode === 'assembly' && (
                  <div className="h-full w-full">
                      <AssemblyGuide />
                  </div>
              )}

              {mode === 'all' && (
                  <div className="h-full overflow-y-auto p-4 md:p-8 no-scrollbar print:p-0 bg-slate-200">
                      {visiblePanels.length === 0 && <div className="text-center text-slate-400 py-20">Нет видимых деталей.</div>}
                      {visiblePanels.map((p, i) => (
                          <DrawingSheet key={p.id} panel={p} index={i} total={visiblePanels.length} />
                      ))}
                  </div>
              )}

              {mode === 'detail' && (
                  <div className="h-full overflow-y-auto p-4 md:p-8 no-scrollbar print:p-0 bg-slate-200 flex flex-col items-center">
                      {selectedPanel ? (
                          <DrawingSheet panel={selectedPanel} index={visiblePanels.findIndex(p => p.id === selectedPanel.id)} total={visiblePanels.length} />
                      ) : (
                          <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-4">
                              <PenTool size={48} className="opacity-20"/>
                              <p>Выберите деталь в 3D виде для отображения чертежа.</p>
                              <button onClick={() => setMode('view_front')} className="text-blue-500 hover:underline">Вернуться к общему виду</button>
                          </div>
                      )}
                  </div>
              )}
          </div>
      </div>
  );
};
