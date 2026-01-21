import React from 'react';
import { Hammer, PackageCheck, CheckSquare } from 'lucide-react';
import AssemblyDiagram from '../AssemblyDiagram';

interface AssemblyStageProps {
  onStageComplete: () => void;
}

const AssemblyStage: React.FC<AssemblyStageProps> = ({ onStageComplete }) => (
  <div className="h-full flex flex-col">
    <div className="flex justify-between items-center mb-4">
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Hammer className="text-emerald-500" /> Цех Сборки
        </h2>
        <p className="text-slate-400 text-sm">Финальная сборка и упаковка</p>
      </div>
      <button
        onClick={onStageComplete}
        className="px-4 py-2 bg-emerald-600 text-white font-bold rounded flex items-center gap-2 hover:bg-emerald-700 shadow-[0_0_20px_rgba(5,150,105,0.4)]"
      >
        <PackageCheck size={16} />{' '}
        <span className="hidden sm:inline">Заказ Готов к Отгрузке</span>
        <span className="sm:hidden">Готово</span>
      </button>
    </div>

    <div className="flex-1 bg-white rounded-xl overflow-hidden shadow-2xl relative border border-slate-600 flex flex-col">
      <div className="flex-1 relative">
        <AssemblyDiagram />
      </div>

      <div className="relative md:absolute md:top-4 md:right-4 w-full md:w-64 bg-slate-900/90 backdrop-blur border-t md:border border-slate-700 rounded-none md:rounded-lg p-4 text-slate-300">
        <h4 className="font-bold text-white mb-3 text-sm flex items-center gap-2">
          <CheckSquare size={14} /> Чек-лист сборщика
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-1 gap-2 text-xs">
          <label className="flex items-center gap-2 cursor-pointer hover:text-white">
            <input type="checkbox" className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0" />
            Сборка корпуса
          </label>
          <label className="flex items-center gap-2 cursor-pointer hover:text-white">
            <input type="checkbox" className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0" />
            Проверка диагоналей
          </label>
          <label className="flex items-center gap-2 cursor-pointer hover:text-white">
            <input type="checkbox" className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0" />
            Задняя стенка
          </label>
          <label className="flex items-center gap-2 cursor-pointer hover:text-white">
            <input type="checkbox" className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0" />
            Ящики/фасады
          </label>
          <label className="flex items-center gap-2 cursor-pointer hover:text-white">
            <input type="checkbox" className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0" />
            Регулировка
          </label>
        </div>
      </div>
    </div>
  </div>
);

export default AssemblyStage;
