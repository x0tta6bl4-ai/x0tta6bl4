import React from 'react';
import { Panel } from '../../types';
import { ScanLine, PanelTop, Lightbulb, Trash2, ArrowUp, ArrowDown, ArrowLeft, ArrowRight } from 'lucide-react';
import { inputClass, labelClass, GrooveSideButton, GrooveIndicator } from './shared';

interface DrillingTabProps {
  panel: Panel;
  onUpdatePanel: (id: string, updates: Partial<Panel>) => void;
  onUpdateGroove: (changes: Record<string, any>) => void;
}

const DrillingTab: React.FC<DrillingTabProps> = ({
  panel,
  onUpdatePanel,
  onUpdateGroove,
}) => {
  const groove = panel.groove || {
    enabled: false,
    side: 'top',
    width: 4,
    depth: 10,
    offset: 16,
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <label className={labelClass}>Паз (Четверть)</label>

        <div className="flex items-center justify-between bg-slate-800 p-3 rounded-t border border-slate-700">
          <span className="text-xs font-bold text-white flex items-center gap-2">
            <ScanLine size={16} /> Активность
          </span>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-slate-400">
              {groove.enabled ? 'Включен' : 'Выключен'}
            </span>
            <input
              type="checkbox"
              checked={groove.enabled || false}
              onChange={(e) => onUpdateGroove({ enabled: e.target.checked })}
              className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-blue-600 focus:ring-blue-500"
            />
          </div>
        </div>

        {groove.enabled && (
          <div className="animate-in slide-in-from-top-2 p-3 bg-slate-800/50 rounded-b border-x border-b border-slate-700/50">
            <div className="flex justify-center mb-4">
              <div className="relative w-32 h-24 bg-slate-700/50 border border-slate-600 rounded flex items-center justify-center">
                <div className="text-[9px] text-slate-500">ДЕТАЛЬ</div>

                <GrooveSideButton
                  side="top"
                  isActive={groove.side === 'top'}
                  onClick={() => onUpdateGroove({ side: 'top' })}
                  icon={<ArrowUp size={12} />}
                  position="-top-3 left-1/2 -translate-x-1/2"
                />
                <GrooveSideButton
                  side="bottom"
                  isActive={groove.side === 'bottom'}
                  onClick={() => onUpdateGroove({ side: 'bottom' })}
                  icon={<ArrowDown size={12} />}
                  position="-bottom-3 left-1/2 -translate-x-1/2"
                />
                <GrooveSideButton
                  side="left"
                  isActive={groove.side === 'left'}
                  onClick={() => onUpdateGroove({ side: 'left' })}
                  icon={<ArrowLeft size={12} />}
                  position="top-1/2 -left-3 -translate-y-1/2"
                />
                <GrooveSideButton
                  side="right"
                  isActive={groove.side === 'right'}
                  onClick={() => onUpdateGroove({ side: 'right' })}
                  icon={<ArrowRight size={12} />}
                  position="top-1/2 -right-3 -translate-y-1/2"
                />

                <GrooveIndicator side={groove.side} />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 mb-4">
              <div>
                <label className={labelClass}>Ширина</label>
                <input
                  type="number"
                  value={groove.width}
                  onChange={(e) => onUpdateGroove({ width: +e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Глубина</label>
                <input
                  type="number"
                  value={groove.depth}
                  onChange={(e) => onUpdateGroove({ depth: +e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Отступ</label>
                <input
                  type="number"
                  value={groove.offset}
                  onChange={(e) => onUpdateGroove({ offset: +e.target.value })}
                  className={inputClass}
                />
              </div>
            </div>

            <div className="flex gap-2 border-t border-slate-700 pt-3">
              <button
                onClick={() =>
                  onUpdateGroove({
                    width: 4,
                    depth: 10,
                    offset: 16,
                  })
                }
                className="flex-1 py-1.5 px-2 bg-slate-700 hover:bg-slate-600 rounded text-[9px] text-white flex items-center justify-center gap-1"
              >
                <PanelTop size={12} /> Под ХДФ
              </button>
              <button
                onClick={() =>
                  onUpdateGroove({
                    width: 16,
                    depth: 8,
                    offset: 10,
                  })
                }
                className="flex-1 py-1.5 px-2 bg-slate-700 hover:bg-slate-600 rounded text-[9px] text-white flex items-center justify-center gap-1"
              >
                <Lightbulb size={12} /> Под LED
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="space-y-2 pt-2 border-t border-slate-800">
        <label className={labelClass}>Список отверстий</label>
        <div className="space-y-2">
          {panel.hardware.map((hw, i) => (
            <div
              key={hw.id}
              className="p-2 bg-slate-900 rounded border border-slate-800 text-[10px] flex justify-between items-center group"
            >
              <div>
                <span className="text-slate-500">#{i + 1}</span>{' '}
                <span className="text-slate-200 font-bold ml-1">{hw.name}</span>
                <div className="mt-1 text-slate-500 font-mono">
                  X:{hw.x} Y:{hw.y} {hw.diameter && `D:${hw.diameter}`}
                </div>
              </div>
              <button
                onClick={() =>
                  onUpdatePanel(panel.id, {
                    hardware: panel.hardware.filter((h) => h.id !== hw.id),
                  })
                }
                className="text-red-500 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition p-2 hover:bg-slate-800 rounded"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
          {panel.hardware.length === 0 && (
            <div className="text-center py-4 text-slate-500 text-xs border border-dashed border-slate-700 rounded">
              Нет присадки
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DrillingTab;
