
import React, { useState } from 'react';
import { useProjectStore } from '../store/projectStore';
import PanelDrawing from './PanelDrawing';
import AssemblyDiagram from './AssemblyDiagram';
import { PenTool, Layers, Printer } from 'lucide-react';

const DrawingView: React.FC = () => {
  const { panels, selectedPanelId } = useProjectStore();
  const panel = panels.find(p => p.id === selectedPanelId) || null;
  const [mode, setMode] = useState<'detail' | 'assembly'>('detail');

  const svgWidth = 900;
  const svgHeight = 700;
  
  // Render Assembly View if selected
  if (mode === 'assembly') {
      return (
          <div className="h-full flex flex-col">
               <div className="bg-slate-200 p-2 flex gap-2 border-b border-slate-300 print:hidden">
                   <button onClick={() => setMode('detail')} className="px-4 py-2 rounded bg-slate-300 hover:bg-white text-slate-700 text-sm font-bold flex items-center gap-2"><PenTool size={16}/> Чертеж Детали</button>
                   <button onClick={() => setMode('assembly')} className="px-4 py-2 rounded bg-blue-600 text-white text-sm font-bold flex items-center gap-2 shadow"><Layers size={16}/> Схема Сборки</button>
                   <div className="flex-1"></div>
                   <button onClick={() => window.print()} className="px-4 py-2 rounded bg-slate-700 text-white text-sm font-bold flex items-center gap-2 hover:bg-slate-600"><Printer size={16}/> Печать</button>
               </div>
               <div className="flex-1">
                   <AssemblyDiagram />
               </div>
          </div>
      );
  }

  // Default Detail View
  if (!panel) {
    return (
      <div className="h-full flex flex-col">
          <div className="bg-slate-200 p-2 flex gap-2 border-b border-slate-300 print:hidden">
              <button className="px-4 py-2 rounded bg-blue-600 text-white text-sm font-bold flex items-center gap-2 shadow"><PenTool size={16}/> Чертеж Детали</button>
              <button onClick={() => setMode('assembly')} className="px-4 py-2 rounded bg-slate-300 hover:bg-white text-slate-700 text-sm font-bold flex items-center gap-2"><Layers size={16}/> Схема Сборки</button>
          </div>
          <div className="flex-1 flex items-center justify-center bg-white text-slate-400">
            Выберите деталь для просмотра чертежа или переключитесь на Схему Сборки
          </div>
      </div>
    );
  }

  const hardware = panel.hardware || [];

  return (
    <div className="h-full flex flex-col bg-slate-100 overflow-hidden print:bg-white">
        <div className="bg-slate-200 p-2 flex gap-2 border-b border-slate-300 print:hidden">
             <button className="px-4 py-2 rounded bg-blue-600 text-white text-sm font-bold flex items-center gap-2 shadow"><PenTool size={16}/> Чертеж Детали</button>
             <button onClick={() => setMode('assembly')} className="px-4 py-2 rounded bg-slate-300 hover:bg-white text-slate-700 text-sm font-bold flex items-center gap-2"><Layers size={16}/> Схема Сборки</button>
             <div className="flex-1"></div>
             <button onClick={() => window.print()} className="px-4 py-2 rounded bg-slate-700 text-white text-sm font-bold flex items-center gap-2 hover:bg-slate-600"><Printer size={16}/> Печать</button>
        </div>
        
        <div className="bg-white border-b border-slate-200 px-4 py-2 flex justify-between items-center shadow-sm print:border-none print:shadow-none">
            <h2 className="font-bold text-slate-700">Рабочий чертеж детали (Чертеж №{panel.id.slice(-4)})</h2>
        </div>
        
        <div className="flex-1 flex flex-col md:flex-row p-4 gap-4 overflow-auto print:overflow-visible">
            {/* SVG Drawing Container */}
            <div className="bg-white shadow-lg border border-slate-300 relative shrink-0 print:shadow-none print:border-black" style={{width: `${svgWidth}px`, height: `${svgHeight}px`}}>
                <PanelDrawing panel={panel} width={svgWidth} height={svgHeight} detailed={true} />
            </div>

            {/* Drilling Table */}
            <div className="bg-white shadow-lg border border-slate-300 w-96 shrink-0 flex flex-col print:shadow-none print:border-black print:w-full">
                 <div className="bg-slate-100 p-2 font-bold text-slate-700 border-b border-slate-200 print:bg-transparent print:border-black">Таблица операций</div>
                 <div className="overflow-auto flex-1 print:overflow-visible">
                     <table className="w-full text-xs text-left">
                         <thead className="bg-slate-50 border-b print:bg-transparent print:border-black">
                             <tr>
                                 <th className="p-2 border-r print:border-black">№</th>
                                 <th className="p-2 border-r print:border-black">Тип / Диаметр</th>
                                 <th className="p-2 border-r print:border-black">X (База)</th>
                                 <th className="p-2">Y (База)</th>
                             </tr>
                         </thead>
                         <tbody>
                             {hardware.length > 0 ? hardware.map((hw, i) => (
                                 <tr key={hw.id} className="border-b hover:bg-slate-50 print:border-black">
                                     <td className="p-2 border-r text-center text-slate-500 font-bold print:text-black print:border-black">{i + 1}</td>
                                     <td className="p-2 border-r print:border-black">
                                         {hw.type === 'screw' && <span className="text-blue-600 font-bold print:text-black">Винт D5 скв.</span>}
                                         {hw.type === 'minifix_cam' && <span className="text-emerald-600 font-bold print:text-black">Эксцентрик D15</span>}
                                         {hw.type === 'minifix_pin' && <span className="text-slate-600 font-bold print:text-black">Шток эксц. D5</span>}
                                         {hw.type === 'dowel' && <span className="text-amber-600 font-bold print:text-black">Шкант D8 (Торец)</span>}
                                         {hw.type === 'dowel_hole' && <span className="text-amber-800 font-bold print:text-black">Отв. Шкант D8</span>}
                                         {hw.type === 'handle' && 'Ручка D5'}
                                         {hw.type === 'shelf_support' && 'Полкодерж. D5'}
                                     </td>
                                     <td className="p-2 border-r font-mono print:border-black">{hw.x}</td>
                                     <td className="p-2 font-mono">{hw.y}</td>
                                 </tr>
                             )) : (
                                 <tr>
                                     <td colSpan={4} className="p-4 text-center text-slate-400 print:text-black">Нет присадки</td>
                                 </tr>
                             )}
                             {panel.groove && panel.groove.enabled && (
                                 <tr className="border-b bg-blue-50 print:bg-transparent print:border-black">
                                     <td className="p-2 border-r text-center text-blue-500 font-bold print:text-black print:border-black">-</td>
                                     <td className="p-2 border-r text-blue-700 print:text-black print:border-black">Паз {panel.groove.width}x{panel.groove.depth}мм (Отступ {panel.groove.offset}мм)</td>
                                     <td className="p-2 border-r font-mono text-center print:border-black">-</td>
                                     <td className="p-2 font-mono text-center">-</td>
                                 </tr>
                             )}
                         </tbody>
                     </table>
                 </div>
            </div>
        </div>
    </div>
  );
};

export default DrawingView;
