import React from 'react';
import { Panel } from '../../types';
import { Box, FileText, ArrowRight, PlayCircle } from 'lucide-react';

interface DesignStageProps {
  panels: Panel[];
  onStageComplete: () => void;
}

const DesignStage: React.FC<DesignStageProps> = ({ panels, onStageComplete }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-8 h-full">
    <div className="bg-[#222] p-8 rounded-xl border border-slate-700 flex flex-col justify-center items-center text-center">
      <Box size={64} className="text-blue-500 mb-4" />
      <h2 className="text-2xl font-bold text-white mb-2">Проектирование завершено</h2>
      <p className="text-slate-400 mb-6">
        3D модель построена, деталировка сформирована. <br />
        Готово к передаче в производство.
      </p>
      <div className="grid grid-cols-2 gap-4 w-full max-w-md text-left bg-[#1a1a1a] p-4 rounded-lg border border-slate-800">
        <div>
          <div className="text-xs text-slate-500">Всего деталей</div>
          <div className="text-xl font-mono text-white">{panels.length} шт</div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Материалы</div>
          <div className="text-xl font-mono text-white">{new Set(panels.map(p => p.materialId)).size} типа</div>
        </div>
      </div>
    </div>
    <div className="space-y-4">
      <div className="bg-[#222] p-6 rounded-xl border border-slate-700">
        <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <FileText size={20} /> Документация
        </h3>
        <button className="w-full py-3 bg-[#333] hover:bg-[#444] rounded flex items-center justify-between px-4 mb-2 transition">
          <span>Коммерческое предложение</span> <ArrowRight size={16} />
        </button>
        <button className="w-full py-3 bg-[#333] hover:bg-[#444] rounded flex items-center justify-between px-4 mb-2 transition">
          <span>Спецификация материалов</span> <ArrowRight size={16} />
        </button>
        <button
          onClick={onStageComplete}
          className="w-full py-4 mt-6 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded flex items-center justify-center gap-2 shadow-lg shadow-blue-900/20"
        >
          <PlayCircle size={20} /> Передать в раскрой
        </button>
      </div>
    </div>
  </div>
);

export default DesignStage;
