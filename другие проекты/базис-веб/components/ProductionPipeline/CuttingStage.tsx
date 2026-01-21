import React, { useState } from 'react';
import { Panel, Material } from '../../types';
import { Scissors, Printer, CheckCircle2 } from 'lucide-react';
import ProductionLabel from './ProductionLabel';
import QRCodeSVG from './QRCodeSVG';

interface CuttingStageProps {
  panels: Panel[];
  materialLibrary: Material[];
  onStageComplete: () => void;
}

const CuttingStage: React.FC<CuttingStageProps> = ({
  panels,
  materialLibrary,
  onStageComplete,
}) => {
  const [viewLabels, setViewLabels] = useState(false);

  return (
    <div className="h-full flex flex-col">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Scissors className="text-orange-500" /> Карта Раскроя
          </h2>
          <p className="text-slate-400 text-sm">Оптимизация листа и печать этикеток</p>
        </div>
        <div className="flex gap-2 w-full md:w-auto">
          <button
            onClick={() => setViewLabels(!viewLabels)}
            className={`flex-1 md:flex-none px-4 py-2 font-bold rounded flex items-center justify-center gap-2 ${
              viewLabels ? 'bg-white text-black' : 'bg-slate-700 text-white'
            }`}
          >
            <Printer size={16} />{' '}
            <span className="hidden sm:inline">{viewLabels ? 'Закрыть Этикетки' : 'Печать Этикеток'}</span>
            <span className="sm:hidden">Этикетки</span>
          </button>
          <button
            onClick={onStageComplete}
            className="flex-1 md:flex-none px-4 py-2 bg-emerald-600 text-white font-bold rounded flex items-center justify-center gap-2 hover:bg-emerald-700"
          >
            <CheckCircle2 size={16} />{' '}
            <span className="hidden sm:inline">Раскрой Завершен</span>
            <span className="sm:hidden">Готово</span>
          </button>
        </div>
      </div>

      {viewLabels ? (
        <div className="flex-1 overflow-auto bg-slate-300 p-8 rounded-xl shadow-inner">
          <div className="flex justify-end mb-4 print:hidden">
            <button
              onClick={() => window.print()}
              className="bg-blue-600 text-white px-4 py-2 rounded font-bold"
            >
              Печать (Ctrl+P)
            </button>
          </div>
          <div className="flex flex-wrap gap-4 justify-center print:block">
            {panels.map((p, i) => (
              <ProductionLabel
                key={p.id}
                panel={p}
                material={materialLibrary.find(m => m.id === p.materialId)}
                orderId="1024"
                index={i}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 overflow-y-auto pb-20">
          {panels.map((p, i) => (
            <div key={p.id} className="bg-white text-black p-3 rounded shadow-lg relative break-inside-avoid">
              <div className="flex justify-between items-start border-b border-black/20 pb-2 mb-2">
                <div>
                  <div className="text-[10px] uppercase font-bold text-slate-500">Det #{i + 1}</div>
                  <div className="font-bold text-lg leading-tight">{p.name}</div>
                </div>
                <QRCodeSVG value={p.id} size={48} />
              </div>
              <div className="flex justify-between text-xs font-mono font-bold">
                <span>{p.width} x {p.height}</span>
                <span>{materialLibrary.find(m => m.id === p.materialId)?.name.substring(0, 10)}...</span>
              </div>
              <div className="mt-2 flex gap-1">
                {(p.edging.top !== 'none' ||
                  p.edging.bottom !== 'none' ||
                  p.edging.left !== 'none' ||
                  p.edging.right !== 'none') && (
                  <span className="px-1 bg-black text-white text-[9px] rounded">EDGE</span>
                )}
                {p.hardware.length > 0 && <span className="px-1 bg-black text-white text-[9px] rounded">DRILL</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CuttingStage;
