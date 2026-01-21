import React from 'react';
import { Panel } from '../../types';
import { Layers, CheckCircle2 } from 'lucide-react';

interface EdgeStageProps {
  panels: Panel[];
  onPanelStatusChange: (id: string, status: 'completed' | 'pending') => void;
  onStageComplete: () => void;
}

const EdgeStage: React.FC<EdgeStageProps> = ({
  panels,
  onPanelStatusChange,
  onStageComplete,
}) => (
  <div className="h-full flex flex-col">
    <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Layers className="text-blue-500" /> Участок Кромления
        </h2>
        <p className="text-slate-400 text-sm">Нанесение кромки согласно карте</p>
      </div>
      <div className="flex gap-4 items-center w-full md:w-auto justify-between md:justify-end">
        <div className="hidden sm:flex items-center gap-2 bg-[#222] px-3 py-1 rounded border border-slate-700">
          <div className="w-3 h-3 bg-red-500 rounded-full"></div>{' '}
          <span className="text-xs text-slate-300">2.0 мм</span>
          <div className="w-3 h-3 bg-blue-500 rounded-full ml-2"></div>{' '}
          <span className="text-xs text-slate-300">0.4 мм</span>
        </div>
        <button
          onClick={onStageComplete}
          className="px-4 py-2 bg-emerald-600 text-white font-bold rounded flex items-center gap-2 hover:bg-emerald-700"
        >
          <CheckCircle2 size={16} />{' '}
          <span className="hidden sm:inline">Кромление Завершено</span>
          <span className="sm:hidden">Готово</span>
        </button>
      </div>
    </div>

    <div className="flex-1 overflow-y-auto space-y-2">
      {panels.map((p, i) => (
        <div key={p.id} className="bg-[#222] p-4 rounded border border-slate-700 flex justify-between items-center group">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 bg-slate-800 rounded flex items-center justify-center font-bold font-mono text-slate-400">
              {i + 1}
            </div>
            <div>
              <div className="font-bold text-white">{p.name}</div>
              <div className="text-xs text-slate-500 font-mono">
                {p.width} x {p.height}
              </div>
            </div>
          </div>

          <div className="relative w-20 h-12 md:w-32 md:h-20 bg-slate-800 border border-slate-600 shrink-0">
            {p.edging.top !== 'none' && (
              <div
                className={`absolute top-0 left-0 right-0 h-1 ${
                  p.edging.top === '2.0' ? 'bg-red-500' : 'bg-blue-500'
                }`}
              />
            )}
            {p.edging.bottom !== 'none' && (
              <div
                className={`absolute bottom-0 left-0 right-0 h-1 ${
                  p.edging.bottom === '2.0' ? 'bg-red-500' : 'bg-blue-500'
                }`}
              />
            )}
            {p.edging.left !== 'none' && (
              <div
                className={`absolute top-0 bottom-0 left-0 w-1 ${
                  p.edging.left === '2.0' ? 'bg-red-500' : 'bg-blue-500'
                }`}
              />
            )}
            {p.edging.right !== 'none' && (
              <div
                className={`absolute top-0 bottom-0 right-0 w-1 ${
                  p.edging.right === '2.0' ? 'bg-red-500' : 'bg-blue-500'
                }`}
              />
            )}
            <div className="absolute inset-0 flex items-center justify-center text-[8px] md:text-[10px] text-slate-600">
              СХЕМА
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() =>
                onPanelStatusChange(p.id, p.productionStatus === 'completed' ? 'pending' : 'completed')
              }
              className={`w-10 h-10 rounded flex items-center justify-center transition ${
                p.productionStatus === 'completed'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-700 text-slate-500 hover:bg-slate-600'
              }`}
            >
              <CheckCircle2 size={20} />
            </button>
          </div>
        </div>
      ))}
    </div>
  </div>
);

export default EdgeStage;
