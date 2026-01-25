
import React, { useMemo, useState, useEffect, useRef } from 'react';
import { useProjectStore } from '../store/projectStore';
import { Panel, TextureType, Material } from '../types';
import { Settings, RefreshCw, Loader2, RotateCcw } from 'lucide-react';

interface NestingViewProps {
  materialLibrary: Material[];
}

const SHEET_W = 2800;
const SHEET_H = 2070;
const TRIM = 10;

// =================================================================================
// OPTIMIZED NESTING WORKER (Guillotine Packer + BSSF Heuristic)
// =================================================================================
const WORKER_CODE = `
const KERF = 4; // Width of the saw blade

self.onmessage = (e) => {
    const { parts, sheetW, sheetH, trim, materialsConfig } = e.data;

    // 1. Group parts by Material ID
    const partsByMat = {};
    parts.forEach(p => {
        if (!partsByMat[p.materialId]) partsByMat[p.materialId] = [];
        partsByMat[p.materialId].push(p);
    });

    const results = {};

    // 2. Process each material group independently
    Object.keys(partsByMat).forEach(matId => {
        const matParts = partsByMat[matId];
        const config = materialsConfig[matId] || { isTextureStrict: false };
        
        // Find best packing by trying different sort orders
        results[matId] = optimizeMaterialGroup(matParts, sheetW, sheetH, trim, config.isTextureStrict, matId);
    });

    self.postMessage(results);
};

/**
 * Runs the packer with multiple sorting strategies and returns the best result (lowest waste).
 */
function optimizeMaterialGroup(parts, sheetW, sheetH, trim, isTextureStrict, matId) {
    if (!parts || parts.length === 0) return [];

    // Strategies: How to sort parts before placing them
    const strategies = [
        { name: 'Area', sort: (a, b) => (b.w * b.h) - (a.w * a.h) }, // Big area first
        { name: 'LongSide', sort: (a, b) => Math.max(b.w, b.h) - Math.max(a.w, a.h) }, // Long parts first
        { name: 'Width', sort: (a, b) => b.w - a.w } // Wide parts first
    ];

    let bestSolution = null;
    let minSheets = Infinity;
    let minWaste = Infinity;

    for(let strat of strategies) {
        // Clone and sort parts
        const sortedParts = parts.map(p => ({...p, placed: false}));
        sortedParts.sort(strat.sort);

        const sheets = [];
        let allPlaced = true;

        // Packing Loop
        while (sortedParts.some(p => !p.placed)) {
            const sheetResult = packSingleSheet(sortedParts, sheetW, sheetH, trim, isTextureStrict, matId);
            
            // Safety break if we can't place remaining parts (e.g. part larger than sheet)
            if (sheetResult.parts.length === 0 && sortedParts.some(p => !p.placed)) {
                 // Mark unplaceable parts to avoid infinite loop
                 sortedParts.forEach(p => { if(!p.placed) p.placed = true; }); 
                 break;
            }

            const usedArea = sheetResult.parts.reduce((acc, p) => acc + (p.w * p.h), 0);
            const totalArea = sheetW * sheetH;
            const waste = 100 - (usedArea / totalArea * 100);
            
            sheets.push({ ...sheetResult, waste });
            
            if (sheets.length > 200) { allPlaced = false; break; } // Watchdog
        }

        if (allPlaced) {
            // Calculate total efficiency score
            const avgWaste = sheets.reduce((acc, s) => acc + s.waste, 0) / sheets.length;
            
            // Prefer fewer sheets, then lower waste
            if (sheets.length < minSheets || (sheets.length === minSheets && avgWaste < minWaste)) {
                minSheets = sheets.length;
                minWaste = avgWaste;
                bestSolution = sheets;
            }
        }
    }

    return bestSolution || [];
}

/**
 * Packs parts onto a single sheet using Guillotine BSSF (Best Short Side Fit).
 */
function packSingleSheet(partsList, sheetW, sheetH, trim, isTextureStrict, activeMatId) {
    const sheetParts = [];
    
    // Initial free rectangle (whole sheet minus trim)
    let freeRects = [{ 
        x: trim, y: trim, 
        w: sheetW - (trim * 2), 
        h: sheetH - (trim * 2) 
    }];

    // --- HELPER: Find best free rect for a part ---
    const findBestFit = (partW, partH, allowRotate) => {
        let bestRectIdx = -1;
        let bestScore = Number.MAX_VALUE; // Minimize this (Short Side Residual)
        let rotated = false;

        for (let i = 0; i < freeRects.length; i++) {
            const r = freeRects[i];
            
            // Check Normal Orientation
            if (r.w >= partW && r.h >= partH) {
                const residualH = r.w - partW;
                const residualV = r.h - partH;
                const score = Math.min(residualH, residualV);
                
                if (score < bestScore) {
                    bestScore = score;
                    bestRectIdx = i;
                    rotated = false;
                }
            }

            // Check Rotated Orientation (if allowed)
            if (allowRotate && r.w >= partH && r.h >= partW) {
                const residualH = r.w - partH;
                const residualV = r.h - partW;
                const score = Math.min(residualH, residualV);

                if (score < bestScore) {
                    bestScore = score;
                    bestRectIdx = i;
                    rotated = true;
                }
            }
        }
        return { index: bestRectIdx, rotated };
    };

    // --- HELPER: Split free rect after placement (Guillotine Split) ---
    const splitFreeRect = (rectIdx, usedW, usedH) => {
        const r = freeRects[rectIdx];
        freeRects.splice(rectIdx, 1); // Remove the used rect

        // We have L-shaped remaining area. Split it into two new rects.
        // Strategy: Maximize the area of the larger remaining rectangle (Shorter Axis Split rule usually)
        
        const wRem = r.w - usedW;
        const hRem = r.h - usedH;
        
        // Horizontal Split vs Vertical Split decisions
        // We generally prefer the split that leaves a rectangle with the larger shorter side (making it less "thin")
        
        let splitHorizontally = (wRem > hRem); 

        if (splitHorizontally) {
             // Split Horizontally: Top Strip + Side Box
             if (hRem > 0) freeRects.push({ x: r.x, y: r.y + usedH + KERF, w: r.w, h: hRem - KERF });
             if (wRem > 0) freeRects.push({ x: r.x + usedW + KERF, y: r.y, w: wRem - KERF, h: usedH });
        } else {
             // Split Vertically: Side Strip + Top Box
             if (wRem > 0) freeRects.push({ x: r.x + usedW + KERF, y: r.y, w: wRem - KERF, h: r.h });
             if (hRem > 0) freeRects.push({ x: r.x, y: r.y + usedH + KERF, w: usedW, h: hRem - KERF });
        }
    };

    // Iterate through UNPLACED parts
    // Note: We iterate linearly through the sorted list. A more advanced packer 
    // would search *all* parts for the global best fit for *current* free rects, 
    // but sorting beforehand gives 95% of the efficiency with O(n) performance.
    
    for (let i = 0; i < partsList.length; i++) {
         const p = partsList[i];
         if (p.placed) continue;

         const allowRotate = !isTextureStrict; 
         const { index, rotated } = findBestFit(p.w, p.h, allowRotate);
         
         if (index !== -1) {
             const r = freeRects[index];
             const placeW = rotated ? p.h : p.w;
             const placeH = rotated ? p.w : p.h;

             // Add to result
             sheetParts.push({
                 id: p.id, name: p.name,
                 x: r.x, y: r.y, w: placeW, h: placeH,
                 finishW: p.w, finishH: p.h,
                 rotated: rotated, materialId: activeMatId
             });

             // Update Free Rects
             splitFreeRect(index, placeW, placeH);
             
             // Mark as placed
             p.placed = true;
         }
    }
    
    // Filter out unusable tiny scraps to keep array size manageable
    freeRects = freeRects.filter(r => r.w > 20 && r.h > 20);
    
    return { parts: sheetParts, freeRects };
}
`;

const NestingView: React.FC<NestingViewProps> = ({ materialLibrary }) => {
  const { panels } = useProjectStore();
  const [activeMatId, setActiveMatId] = useState<string | null>(null);
  
  // Store results for all materials: { [matId]: Sheet[] }
  const [allResults, setAllResults] = useState<Record<string, any[]>>({});
  const [isCalculating, setIsCalculating] = useState(false);
  const workerRef = useRef<Worker | null>(null);

  // Initialize Worker
  useEffect(() => {
    const blob = new Blob([WORKER_CODE], { type: 'application/javascript' });
    const url = URL.createObjectURL(blob);
    workerRef.current = new Worker(url);
    workerRef.current.onmessage = (e) => {
        setAllResults(e.data);
        setIsCalculating(false);
    };
    return () => {
        workerRef.current?.terminate();
        URL.revokeObjectURL(url);
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

  // Run Global Optimization when panels change
  useEffect(() => {
    if (!workerRef.current || panels.length === 0) return;
    
    setIsCalculating(true);

    // Prepare lightweight payload for worker
    const parts = panels.map(p => ({
         id: p.id,
         name: p.name,
         // We use full dimensions (with edging compensation logic if needed, but here simple bounding box)
         w: p.width,
         h: p.height,
         materialId: p.materialId,
         placed: false
    }));

    const materialsConfig: Record<string, { isTextureStrict: boolean }> = {};
    materialLibrary.forEach(m => {
        materialsConfig[m.id] = { isTextureStrict: m.isTextureStrict };
    });

    workerRef.current.postMessage({
        parts,
        sheetW: SHEET_W,
        sheetH: SHEET_H,
        trim: TRIM,
        materialsConfig
    });

  }, [panels, materialLibrary]);

  // Global Stats Calculation
  const globalStats = useMemo(() => {
      let totalSheets = 0;
      let totalArea = 0;
      let weightedWaste = 0;
      let sheetCountForWaste = 0;

      Object.values(allResults).forEach((sheets: any[]) => {
          totalSheets += sheets.length;
          sheets.forEach(s => {
              totalArea += s.parts.reduce((acc: number, p: any) => acc + (p.finishW * p.finishH), 0);
              weightedWaste += s.waste;
              sheetCountForWaste++;
          });
      });

      return {
          totalSheets,
          totalArea: totalArea / 1000000,
          avgWaste: sheetCountForWaste > 0 ? weightedWaste / sheetCountForWaste : 0
      };
  }, [allResults]);

  const activeSheets = activeMatId ? (allResults[activeMatId] || []) : [];
  const activeMaterial = materialLibrary.find(m => m.id === activeMatId);

  return (
    <div className="flex flex-col h-full bg-[#1a1a1a] text-slate-300">
      {/* Header */}
      <div className="bg-[#222] border-b border-slate-700 p-4 flex justify-between items-center shadow-md z-10">
          <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2"><Settings size={20} className="text-blue-500"/> Карта раскроя</h2>
              <div className="flex gap-4 mt-1">
                  <p className="text-xs text-slate-500 font-mono">Лист: {SHEET_W}x{SHEET_H}мм</p>
                  {globalStats.totalSheets > 0 && (
                      <>
                        <p className="text-xs text-orange-400 font-mono font-bold">Всего листов: {globalStats.totalSheets}</p>
                        <p className="text-xs text-red-400 font-mono font-bold">Средний отход: {globalStats.avgWaste.toFixed(1)}%</p>
                        <p className="text-xs text-blue-400 font-mono font-bold">Общая площадь: {globalStats.totalArea.toFixed(2)} м²</p>
                      </>
                  )}
              </div>
          </div>
          <div className="flex gap-2 overflow-x-auto max-w-md no-scrollbar">
             {materialsInUse.map(m => (
                 <button 
                    key={m.id}
                    onClick={() => setActiveMatId(m.id)}
                    className={`px-3 py-1 text-xs rounded border transition flex flex-col items-center min-w-[80px] ${activeMatId === m.id ? 'bg-blue-600 border-blue-500 text-white' : 'bg-slate-800 border-slate-600 hover:bg-slate-700'}`}
                 >
                     <span className="font-bold truncate max-w-full">{m.name}</span>
                     <span className="text-[10px] opacity-70">
                         {(allResults[m.id] || []).length} лист(ов)
                     </span>
                 </button>
             ))}
          </div>
      </div>

      {/* Sheets Grid */}
      <div className="flex-1 overflow-y-auto p-8 relative">
          
          {isCalculating && (
              <div className="absolute inset-0 bg-[#1a1a1a]/80 flex flex-col items-center justify-center z-50 backdrop-blur-sm">
                  <Loader2 className="animate-spin text-blue-500 mb-2" size={48} />
                  <span className="text-lg font-bold text-white">Оптимизация раскроя (BSSF Alg)...</span>
              </div>
          )}

          <div className="grid grid-cols-1 gap-12 max-w-5xl mx-auto">
              {!isCalculating && activeSheets.length === 0 && (
                  <div className="text-center text-slate-500 py-20">Нет деталей для раскроя выбранного материала</div>
              )}
              {activeSheets.map((sheet, idx) => (
                  <div key={idx} className="bg-[#2a2a2a] p-1 rounded-sm shadow-2xl relative print:break-inside-avoid">
                      <div className="absolute -top-6 left-0 flex justify-between w-full px-1">
                          <span className="text-sm font-bold text-slate-300">ЛИСТ {idx + 1} ({activeMaterial?.name})</span>
                          <span className="text-xs font-mono text-orange-400">Отход: {sheet.waste.toFixed(1)}%</span>
                      </div>
                      
                      <div className="relative bg-[#1a1a1a] border border-slate-600 mx-auto overflow-hidden" 
                           style={{ width: '100%', aspectRatio: `${SHEET_W} / ${SHEET_H}` }}>
                           
                           {/* Sheet Texture Background */}
                           <div className="absolute inset-0 opacity-10 pointer-events-none" 
                                style={{
                                    backgroundImage: `repeating-linear-gradient(${activeMaterial?.isTextureStrict ? 0 : 45}deg, transparent, transparent 10px, #ffffff 10px, #ffffff 11px)`
                                }}>
                           </div>

                          {sheet.parts.map((p: any) => (
                              <div key={p.id} 
                                   className="absolute border border-slate-900 bg-amber-100/10 flex flex-col items-center justify-center hover:bg-blue-500/30 transition group print:bg-white print:border-black"
                                   style={{
                                       left: `${(p.x / SHEET_W) * 100}%`,
                                       top: `${(p.y / SHEET_H) * 100}%`,
                                       width: `${(p.w / SHEET_W) * 100}%`,
                                       height: `${(p.h / SHEET_H) * 100}%`,
                                   }}>
                                   <div className="absolute inset-0 border-[0.5px] border-amber-500/50 pointer-events-none"></div>
                                   {/* Texture Direction Indicator on Part */}
                                   {activeMaterial?.isTextureStrict && (
                                       <div className="absolute inset-0 flex items-center justify-center opacity-20 pointer-events-none overflow-hidden">
                                           <div className={`w-full h-full border-t-2 border-b-2 border-white ${p.rotated ? 'rotate-90' : ''}`} style={{ height: '50%'}}></div>
                                       </div>
                                   )}

                                   <div className="text-[10px] font-bold text-slate-300 truncate px-1 w-full text-center group-hover:scale-110 transition print:text-black z-10">
                                       №{p.id.slice(-3)}
                                   </div>
                                   <div className="text-[8px] text-slate-500 font-mono print:text-black z-10 flex items-center justify-center gap-1">
                                       {p.finishW}x{p.finishH}
                                       {p.rotated && <RotateCcw size={8} className="text-blue-400"/>}
                                   </div>
                              </div>
                          ))}
                          
                          {sheet.freeRects.map((r: any, i: number) => (
                              (r.w > 200 && r.h > 200) && (
                                <div key={i}
                                    className="absolute bg-green-900/10 border border-green-900/20 flex items-center justify-center"
                                    style={{
                                        left: `${(r.x / SHEET_W) * 100}%`,
                                        top: `${(r.y / SHEET_H) * 100}%`,
                                        width: `${(r.w / SHEET_W) * 100}%`,
                                        height: `${(r.h / SHEET_H) * 100}%`,
                                    }}
                                >
                                    <span className="text-[10px] text-green-700/50 -rotate-45 font-bold">{Math.round(r.w)}x{Math.round(r.h)}</span>
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
