import React, { useMemo } from 'react';
import { Panel, ProductionNorms, ProductionStage } from '../../types';
import { Scissors, Layers, Factory, Hammer, Clock, Scan } from 'lucide-react';

interface RightSidebarProps {
  panels: Panel[];
  currentGlobalStage: ProductionStage;
  norms: ProductionNorms;
  scannerInput: string;
  onScannerInputChange: (value: string) => void;
  onScan: (e: React.FormEvent) => void;
}

const RightSidebar: React.FC<RightSidebarProps> = ({
  panels,
  currentGlobalStage,
  norms,
  scannerInput,
  onScannerInputChange,
  onScan,
}) => {
  const stageStats = useMemo(() => {
    const completed = panels.filter(p => p.productionStatus === 'completed').length;
    const total = panels.length;
    const progress = total > 0 ? Math.round((completed / total) * 100) : 0;
    return { completed, total, progress };
  }, [panels]);

  return (
    <div className="w-full md:w-80 bg-[#1a1a1a] border-t md:border-t-0 md:border-l border-slate-700 flex flex-col overflow-y-auto print:hidden order-2 md:order-2 shrink-0 max-h-[300px] md:max-h-none">
      <div className="p-4 border-b border-slate-700">
        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Статус Заказа</div>
        <div className="text-lg font-bold text-white mb-1">Заказ #2026-001</div>
        <div className="flex items-center gap-2 text-sm">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="text-emerald-400 capitalize">{currentGlobalStage}</span>
        </div>
      </div>

      <div className="p-4 border-b border-slate-700">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs font-bold text-slate-500 uppercase">Прогресс этапа</span>
          <span className="text-xs font-mono text-blue-400">{stageStats.progress}%</span>
        </div>
        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
          <div className="h-full bg-blue-600 transition-all duration-500" style={{ width: `${stageStats.progress}%` }}></div>
        </div>
        <div className="text-xs text-slate-500 mt-2 text-right">
          {stageStats.completed} из {stageStats.total} деталей
        </div>
      </div>

      <div className="hidden md:block p-4 border-b border-slate-700">
        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Время (План)</div>
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="flex items-center gap-2">
              <Scissors size={14} /> Раскрой
            </span>
            <span className="font-mono text-slate-300">{norms.cuttingTime} м</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="flex items-center gap-2">
              <Layers size={14} /> Кромка
            </span>
            <span className="font-mono text-slate-300">{norms.edgingTime} м</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="flex items-center gap-2">
              <Factory size={14} /> Присадка
            </span>
            <span className="font-mono text-slate-300">{norms.drillingTime} м</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="flex items-center gap-2">
              <Hammer size={14} /> Сборка
            </span>
            <span className="font-mono text-slate-300">{norms.assemblyTime} м</span>
          </div>
          <div className="pt-2 border-t border-slate-800 flex justify-between text-sm font-bold text-white">
            <span>ИТОГО:</span>
            <span className="flex items-center gap-1">
              <Clock size={14} className="text-orange-500" /> {Math.ceil(norms.totalTimeMinutes / 60)}ч{' '}
              {norms.totalTimeMinutes % 60}м
            </span>
          </div>
        </div>
      </div>

      <div className="p-4 mt-auto">
        <div className="bg-[#111] border border-slate-700 p-4 rounded-xl">
          <div className="text-xs font-bold text-slate-500 uppercase mb-2 flex items-center gap-2">
            <Scan size={14} /> Сканер QR
          </div>
          <form onSubmit={onScan}>
            <input
              type="text"
              value={scannerInput}
              onChange={e => onScannerInputChange(e.target.value)}
              placeholder="Сканировать ID..."
              className="w-full bg-[#222] border border-slate-600 rounded p-2 text-sm text-white focus:border-blue-500 focus:outline-none"
            />
          </form>
        </div>
      </div>
    </div>
  );
};

export default RightSidebar;
