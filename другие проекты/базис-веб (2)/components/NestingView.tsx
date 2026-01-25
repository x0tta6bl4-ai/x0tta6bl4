
import React, { useMemo, useState, useEffect, useRef } from 'react';
import { useProjectStore } from '../store/projectStore';
import { Material } from '../types';
import { Settings, RefreshCw, Loader2, RotateCcw, Download, Printer, Box } from 'lucide-react';
import { SheetNestingService, SHEET_SIZES } from '../services/SheetNesting';

interface NestingViewProps {
  materialLibrary: Material[];
}

const NestingView: React.FC<NestingViewProps> = ({ materialLibrary }) => {
  const { panels } = useProjectStore();
  const [activeMatId, setActiveMatId] = useState<string | null>(null);
  const [selectedSheetSize, setSelectedSheetSize] = useState(SHEET_SIZES[1]); // Default 2440x1830
  
  // Store results for all materials: { [matId]: Sheet[] }
  const [allResults, setAllResults] = useState<Record<string, any[]>>({});
  const [isCalculating, setIsCalculating] = useState(false);
  const workerRef = useRef<Worker | null>(null);

  // Initialize Worker using the Service
  useEffect(() => {
    workerRef.current = SheetNestingService.createWorker();
    workerRef.current.onmessage = (e) => {
        setAllResults(e.data);
        setIsCalculating(false);
    };
    return () => {
        workerRef.current?.terminate();
    };
  }, []);

  const materialsInUse = useMemo(() => {
      const ids = Array.from(new Set(panels.map(p => p.materialId)));
      return ids.map(id => materialLibrary.find(m => m.id === id)).filter(Boolean) as Material[];
  }, [panels, materialLibrary]);

  useEffect(() => {
      if (!activeMatId && materialsInUse.length > 0) {
          setActiveMatId(materialsInUse[0].id);
      }
  }, [materialsInUse, activeMatId]);

  // Run Global Optimization
  const runOptimization = () => {
    if (!workerRef.current || panels.length === 0) return;
    
    setIsCalculating(true);

    const parts = panels.map(p => ({
         id: p.id,
         name: p.name,
         // Add 2mm to dimensions if edging is 2mm? (Logic usually handled in PanelDrawing, assuming panels here are 'cut size')
         // For this demo, we assume panel dimensions are final cut dimensions.
         w: p.width,
         h: p.height,
         materialId: p.materialId,
         layer: p.layer, // Pass layer for coloring
         placed: false
    }));

    const materialsConfig: Record<string, { isTextureStrict: boolean }> = {};
    materialLibrary.forEach(m => {
        materialsConfig[m.id] = { isTextureStrict: m.isTextureStrict };
    });

    workerRef.current.postMessage({
        parts,
        sheetW: selectedSheetSize.w,
        sheetH: selectedSheetSize.h,
        trim: 10,
        materialsConfig
    });
  };

  useEffect(() => {
      runOptimization();
  }, [panels, selectedSheetSize]); // Re-run when panels or sheet size changes

  // Global Stats
  const globalStats = useMemo(() => {
      let totalSheets = 0;
      let totalArea = 0;
      let totalUsed = 0;

      Object.values(allResults).forEach((sheets: any[]) => {
          totalSheets += sheets.length;
          sheets.forEach(s => {
              const usedOnSheet = s.parts.reduce((acc: number, p: any) => acc + (p.finishW * p.finishH), 0);
              totalUsed += usedOnSheet;
              totalArea += (selectedSheetSize.w * selectedSheetSize.h);
          });
      });

      const totalWastePct = totalArea > 0 ? 100 - (totalUsed / totalArea * 100) : 0;

      return {
          totalSheets,
          totalArea: totalArea / 1000000,
          waste: totalWastePct
      };
  }, [allResults, selectedSheetSize]);

  const activeSheets = activeMatId ? (allResults[activeMatId] || []) : [];
  const activeMaterial = materialLibrary.find(m => m.id === activeMatId);

  const getLayerColor = (layer: string) => {
      switch(layer) {
          case 'shelves': return 'bg-blue-600 border-blue-400';
          case 'body': return 'bg-emerald-600 border-emerald-400';
          case 'facade': return 'bg-orange-600 border-orange-400';
          case 'back': return 'bg-slate-500 border-slate-400';
          default: return 'bg-slate-700 border-slate-500';
      }
  };

  const handleExportCSV = () => {
      if (!activeMaterial) return;
      const csv = SheetNestingService.generateCSV(activeSheets, activeMaterial.name);
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `cutting_map_${activeMatId}.csv`;
      link.click();
  };

  return (
    <div className="flex flex-col h-full bg-[#1a1a1a] text-slate-300">
      {/* Header */}
      <div className="bg-[#222] border-b border-slate-700 p-4 flex flex-col lg:flex-row justify-between items-start lg:items-center shadow-md z-10 gap-4">
          <div className="flex flex-col gap-2">
              <h2 className="text-xl font-bold text-white flex items-center gap-2"><Settings size={20} className="text-blue-500"/> Карта раскроя</h2>
              
              <div className="flex items-center gap-4">
                  <select 
                    value={selectedSheetSize.id}
                    onChange={(e) => {
                        const s = SHEET_SIZES.find(sz => sz.id === e.target.value);
                        if(s) setSelectedSheetSize(s);
                    }}
                    className="bg-[#111] border border-slate-600 text-xs text-white rounded px-2 py-1 outline-none focus:border-blue-500"
                  >
                      {SHEET_SIZES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                  </select>

                  {globalStats.totalSheets > 0 && (
                      <div className="flex gap-3 text-xs font-mono">
                        <span className="text-orange-400 font-bold">{globalStats.totalSheets} лист(ов)</span>
                        <span className={`${globalStats.waste < 15 ? 'text-green-400' : 'text-red-400'} font-bold`}>Отход: {globalStats.waste.toFixed(1)}%</span>
                      </div>
                  )}
              </div>
          </div>

          <div className="flex gap-2 items-center">
             <div className="flex gap-1 mr-4 overflow-x-auto max-w-[200px] lg:max-w-md no-scrollbar">
                {materialsInUse.map(m => (
                    <button 
                        key={m.id}
                        onClick={() => setActiveMatId(m.id)}
                        className={`px-3 py-1 text-xs rounded border transition flex flex-col items-center min-w-[80px] shrink-0 ${activeMatId === m.id ? 'bg-blue-600 border-blue-500 text-white' : 'bg-slate-800 border-slate-600 hover:bg-slate-700'}`}
                    >
                        <span className="font-bold truncate max-w-full">{m.name}</span>
                        <span className="text-[10px] opacity-70">
                            {(allResults[m.id] || []).length} л.
                        </span>
                    </button>
                ))}
             </div>
             
             <div className="flex gap-1">
                 <button onClick={handleExportCSV} className="p-2 bg-slate-700 hover:bg-slate-600 text-white rounded" title="Скачать CSV">
                     <Download size={18}/>
                 </button>
                 <button onClick={() => window.print()} className="p-2 bg-slate-700 hover:bg-slate-600 text-white rounded" title="Печать">
                     <Printer size={18}/>
                 </button>
                 <button onClick={runOptimization} className="p-2 bg-blue-600 hover:bg-blue-700 text-white rounded" title="Пересчитать">
                     <RefreshCw size={18} className={isCalculating ? 'animate-spin' : ''}/>
                 </button>
             </div>
          </div>
      </div>

      {/* Legend */}
      <div className="bg-[#1f1f1f] px-4 py-1 flex gap-4 text-[10px] text-slate-400 border-b border-slate-800 justify-center print:hidden">
          <span className="flex items-center gap-1"><div className="w-2 h-2 bg-emerald-500 rounded-full"></div> Корпус</span>
          <span className="flex items-center gap-1"><div className="w-2 h-2 bg-blue-500 rounded-full"></div> Полки</span>
          <span className="flex items-center gap-1"><div className="w-2 h-2 bg-orange-500 rounded-full"></div> Фасад</span>
          <span className="flex items-center gap-1"><div className="w-2 h-2 bg-slate-500 rounded-full"></div> Задняя стенка</span>
          <span className="flex items-center gap-1"><div className="w-2 h-2 bg-red-500/20 border border-red-500/50"></div> Обрезки</span>
      </div>

      {/* Sheets Grid */}
      <div className="flex-1 overflow-y-auto p-8 relative">
          
          {isCalculating && (
              <div className="absolute inset-0 bg-[#1a1a1a]/80 flex flex-col items-center justify-center z-50 backdrop-blur-sm">
                  <Loader2 className="animate-spin text-blue-500 mb-2" size={48} />
                  <span className="text-lg font-bold text-white">Оптимизация раскроя...</span>
              </div>
          )}

          <div className="grid grid-cols-1 gap-12 max-w-5xl mx-auto">
              {!isCalculating && activeSheets.length === 0 && (
                  <div className="text-center text-slate-500 py-20 flex flex-col items-center gap-4">
                      <Box size={48} className="opacity-20"/>
                      <p>Нет деталей для раскроя выбранного материала</p>
                  </div>
              )}
              {activeSheets.map((sheet, idx) => (
                  <div key={idx} className="bg-[#2a2a2a] p-1 rounded-sm shadow-2xl relative print:break-inside-avoid print:mb-8 print:bg-white print:shadow-none">
                      <div className="absolute -top-6 left-0 flex justify-between w-full px-1 print:text-black">
                          <span className="text-sm font-bold text-slate-300 print:text-black">ЛИСТ {idx + 1} ({activeMaterial?.name})</span>
                          <span className="text-xs font-mono text-orange-400 print:text-black">Отход: {sheet.waste.toFixed(1)}%</span>
                      </div>
                      
                      <div className="relative bg-[#1a1a1a] border border-slate-600 mx-auto overflow-hidden print:bg-white print:border-black" 
                           style={{ width: '100%', aspectRatio: `${selectedSheetSize.w} / ${selectedSheetSize.h}` }}>
                           
                           {/* Sheet Texture Background */}
                           <div className="absolute inset-0 opacity-10 pointer-events-none" 
                                style={{
                                    backgroundImage: `repeating-linear-gradient(${activeMaterial?.isTextureStrict ? 0 : 45}deg, transparent, transparent 10px, #ffffff 10px, #ffffff 11px)`
                                }}>
                           </div>

                          {sheet.parts.map((p: any) => (
                              <div key={p.id} 
                                   className={`absolute border flex flex-col items-center justify-center hover:scale-[1.02] transition group print:bg-white print:border-black print:text-black shadow-sm ${getLayerColor(p.layer)}`}
                                   style={{
                                       left: `${(p.x / selectedSheetSize.w) * 100}%`,
                                       top: `${(p.y / selectedSheetSize.h) * 100}%`,
                                       width: `${(p.w / selectedSheetSize.w) * 100}%`,
                                       height: `${(p.h / selectedSheetSize.h) * 100}%`,
                                   }}>
                                   {/* Texture Direction Indicator */}
                                   {activeMaterial?.isTextureStrict && (
                                       <div className="absolute inset-0 flex items-center justify-center opacity-30 pointer-events-none overflow-hidden">
                                           <div className={`w-full h-0.5 bg-white ${p.rotated ? 'rotate-90' : ''}`}></div>
                                       </div>
                                   )}

                                   <div className="text-[10px] font-bold text-white truncate px-1 w-full text-center z-10 print:text-black leading-tight">
                                       №{p.id.slice(-3)}
                                   </div>
                                   <div className="text-[8px] text-white/80 font-mono z-10 flex items-center justify-center gap-1 print:text-black">
                                       {p.finishW}x{p.finishH}
                                       {p.rotated && <RotateCcw size={8} className="text-white print:text-black"/>}
                                   </div>
                              </div>
                          ))}
                          
                          {/* Waste Visualization */}
                          {sheet.freeRects.map((r: any, i: number) => (
                              (r.w > 50 && r.h > 50) && (
                                <div key={i}
                                    className="absolute bg-red-900/10 border border-red-900/20 flex items-center justify-center print:hidden"
                                    style={{
                                        left: `${(r.x / selectedSheetSize.w) * 100}%`,
                                        top: `${(r.y / selectedSheetSize.h) * 100}%`,
                                        width: `${(r.w / selectedSheetSize.w) * 100}%`,
                                        height: `${(r.h / selectedSheetSize.h) * 100}%`,
                                    }}
                                >
                                    <span className="text-[9px] text-red-500/30 -rotate-45 font-bold">{Math.round(r.w)}x{Math.round(r.h)}</span>
                                </div>
                              )
                          ))}
                      </div>
                  </div>
              ))}
          </div>
      </div>
    </div>
  );
};

export default NestingView;
