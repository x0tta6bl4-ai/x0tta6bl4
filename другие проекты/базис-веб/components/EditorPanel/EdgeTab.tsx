import React from 'react';
import { Panel, EdgeThickness } from '../../types';
import { Settings2 } from 'lucide-react';

interface EdgeTabProps {
  panel: Panel;
  onUpdatePanel: (id: string, updates: Partial<Panel>) => void;
}

const EdgeTab: React.FC<EdgeTabProps> = ({ panel, onUpdatePanel }) => {
  const sides = ['top', 'bottom', 'left', 'right'] as const;

  return (
    <div className="space-y-3">
      {sides.map((side) => (
        <div
          key={side}
          className="flex items-center justify-between p-2 bg-slate-800 rounded border border-slate-700"
        >
          <span className="text-[10px] font-bold uppercase text-slate-400 w-12">
            {side}
          </span>
          <select
            value={panel.edging[side]}
            onChange={(e) =>
              onUpdatePanel(panel.id, {
                edging: {
                  ...panel.edging,
                  [side]: e.target.value as EdgeThickness,
                },
              })
            }
            className="bg-slate-900 border-none text-xs rounded p-1 focus:ring-0 text-slate-200 w-24"
          >
            <option value="none">Нет</option>
            <option value="0.4">0.4 мм</option>
            <option value="1.0">1.0 мм</option>
            <option value="2.0">2.0 мм</option>
          </select>
        </div>
      ))}
      <div className="bg-blue-900/20 p-3 rounded-lg border border-blue-800/50 flex items-start gap-2 mt-4">
        <Settings2 size={16} className="text-blue-500 mt-0.5" />
        <p className="text-[10px] text-blue-300 leading-relaxed">
          Кромка 2.0мм автоматически уменьшает пильный размер детали на 2мм с
          каждой стороны.
        </p>
      </div>
    </div>
  );
};

export default EdgeTab;
