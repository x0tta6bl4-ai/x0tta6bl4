import React from 'react';
import { Panel, Material } from '../../types';
import { Factory, FileDown, CheckCircle2 } from 'lucide-react';

interface DrillingStageProps {
  panels: Panel[];
  materialLibrary: Material[];
  onGenerateCNC: () => void;
  onPanelStatusChange: (id: string, status: 'completed' | 'pending') => void;
  onStageComplete: () => void;
}

const DrillingStage: React.FC<DrillingStageProps> = ({
  panels,
  materialLibrary,
  onGenerateCNC,
  onPanelStatusChange,
  onStageComplete,
}) => (
  <div className="h-full flex flex-col">
    <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Factory className="text-purple-500" /> Участок Присадки (ЧПУ)
        </h2>
        <p className="text-slate-400 text-sm">Сверление отверстий</p>
      </div>
      <div className="flex gap-2 w-full md:w-auto">
        <button
          onClick={onGenerateCNC}
          className="flex-1 md:flex-none px-4 py-2 bg-purple-600 text-white font-bold rounded flex items-center justify-center gap-2 hover:bg-purple-700"
        >
          <FileDown size={16} /> <span className="hidden sm:inline">CSV для ЧПУ</span>
          <span className="sm:hidden">CSV</span>
        </button>
        <button
          onClick={onStageComplete}
          className="flex-1 md:flex-none px-4 py-2 bg-emerald-600 text-white font-bold rounded flex items-center justify-center gap-2 hover:bg-emerald-700"
        >
          <CheckCircle2 size={16} /> <span className="hidden sm:inline">Присадка Завершена</span>
          <span className="sm:hidden">Готово</span>
        </button>
      </div>
    </div>

    <div className="flex-1 overflow-y-auto">
      <table className="w-full text-left text-sm text-slate-300">
        <thead className="bg-[#222] text-xs uppercase text-slate-500 font-bold sticky top-0">
          <tr>
            <th className="p-3">ID</th>
            <th className="p-3">Деталь</th>
            <th className="p-3 hidden sm:table-cell">Отверстия</th>
            <th className="p-3 hidden sm:table-cell">Типы</th>
            <th className="p-3 text-center">Статус</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {panels
            .filter(p => p.hardware.length > 0 || p.groove?.enabled)
            .map((p, i) => (
              <tr key={p.id} className="hover:bg-slate-800/50">
                <td className="p-3 font-mono text-slate-500">#{i + 1}</td>
                <td className="p-3 font-bold">
                  {p.name}
                  <div className="sm:hidden text-xs font-normal text-slate-500">
                    {p.hardware.length} отв.
                  </div>
                </td>
                <td className="p-3 font-mono hidden sm:table-cell">{p.hardware.length} шт</td>
                <td className="p-3 hidden sm:table-cell">
                  <div className="flex gap-1 flex-wrap">
                    {Array.from(new Set(p.hardware.map(h => h.type))).map((t: string) => (
                      <span key={t} className="px-1.5 py-0.5 bg-slate-700 rounded text-[10px] text-slate-300 uppercase">
                        {t}
                      </span>
                    ))}
                    {p.groove?.enabled && (
                      <span className="px-1.5 py-0.5 bg-blue-900/50 text-blue-300 rounded text-[10px] uppercase">
                        ПАЗ
                      </span>
                    )}
                  </div>
                </td>
                <td className="p-3 text-center">
                  <button
                    onClick={() =>
                      onPanelStatusChange(p.id, p.productionStatus === 'completed' ? 'pending' : 'completed')
                    }
                    className={`px-3 py-1 rounded text-xs font-bold ${
                      p.productionStatus === 'completed'
                        ? 'bg-emerald-900/50 text-emerald-400 border border-emerald-500/30'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}
                  >
                    {p.productionStatus === 'completed' ? 'ГОТОВО' : 'ОЖИДАНИЕ'}
                  </button>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  </div>
);

export default DrillingStage;
