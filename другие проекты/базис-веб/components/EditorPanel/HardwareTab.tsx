import React from 'react';
import { CircleDot, Hammer, Wrench, Anchor } from 'lucide-react';

interface HardwareTabProps {
  onAddHardwarePreset: (preset: 'hinge' | 'rail' | 'handle' | 'mounting') => void;
}

const HardwareTab: React.FC<HardwareTabProps> = ({ onAddHardwarePreset }) => (
  <div className="space-y-4">
    <div className="grid grid-cols-1 gap-2">
      <button
        onClick={() => onAddHardwarePreset('hinge')}
        className="p-3 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 flex items-center gap-3 transition"
      >
        <div className="p-2 bg-blue-900/30 rounded text-blue-500">
          <CircleDot size={18} />
        </div>
        <div className="text-left">
          <div className="text-xs font-bold text-white">Добавить Петли</div>
          <div className="text-[10px] text-slate-500">Blum Clip Top (пара)</div>
        </div>
      </button>
      <button
        onClick={() => onAddHardwarePreset('handle')}
        className="p-3 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 flex items-center gap-3 transition"
      >
        <div className="p-2 bg-emerald-900/30 rounded text-emerald-500">
          <Hammer size={18} />
        </div>
        <div className="text-left">
          <div className="text-xs font-bold text-white">Добавить Ручку</div>
          <div className="text-[10px] text-slate-500">Скоба 128мм (центр)</div>
        </div>
      </button>
      <button
        onClick={() => onAddHardwarePreset('rail')}
        className="p-3 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 flex items-center gap-3 transition"
      >
        <div className="p-2 bg-purple-900/30 rounded text-purple-500">
          <Wrench size={18} />
        </div>
        <div className="text-left">
          <div className="text-xs font-bold text-white">Добавить Напр</div>
          <div className="text-[10px] text-slate-500">Шариковая 450мм</div>
        </div>
      </button>
      <button
        onClick={() => onAddHardwarePreset('mounting')}
        className="p-3 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 flex items-center gap-3 transition"
      >
        <div className="p-2 bg-orange-900/30 rounded text-orange-500">
          <Anchor size={18} />
        </div>
        <div className="text-left">
          <div className="text-xs font-bold text-white">Добавить Крепеж</div>
          <div className="text-[10px] text-slate-500">Эксцентрики (4 шт)</div>
        </div>
      </button>
    </div>
    <p className="text-[10px] text-slate-500 text-center mt-4">
      Добавление фурнитуры автоматически создает отверстия в разделе
      "Присадка".
    </p>
  </div>
);

export default HardwareTab;
