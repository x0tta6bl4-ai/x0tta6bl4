
import React, { useState, useEffect } from 'react';
import { Shelf, CabinetMaterialType } from '../types';
import { 
  Trash2, ArrowUp, Weight, Ruler, AlertTriangle, 
  CheckCircle2, XCircle, Settings2, X
} from 'lucide-react';

interface ShelfInfoPanelProps {
  shelf: Shelf;
  index: number;
  cabinetWidth: number;
  cabinetDepth: number;
  material: CabinetMaterialType;
  maxHeight: number;
  validationError?: string;
  validationWarning?: string;
  isSelected?: boolean;
  onSelect?: () => void;
  onUpdate: (updated: Shelf) => void;
  onDelete: () => void;
}

export const ShelfInfoPanel: React.FC<ShelfInfoPanelProps> = ({
  shelf, index, cabinetWidth, cabinetDepth, material, maxHeight,
  validationError, validationWarning, isSelected, onSelect, onUpdate, onDelete
}) => {
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [localY, setLocalY] = useState(shelf.y);

  // Sync local state when prop changes (external update or undo/redo)
  useEffect(() => {
      setLocalY(shelf.y);
  }, [shelf.y]);

  // Heuristic load calculation
  const getLoadCapacity = () => {
      let baseLoad = 30; // kg
      if (material === 'Дуб' || material === 'Бетон') baseLoad += 15;
      if (cabinetWidth > 800) baseLoad -= 10;
      return `${baseLoad} кг`;
  };

  // Status logic
  const statusColor = validationError ? 'text-red-500' : validationWarning ? 'text-orange-500' : 'text-emerald-500';
  const StatusIcon = validationError ? XCircle : validationWarning ? AlertTriangle : CheckCircle2;
  
  // Dynamic border based on state
  let borderColor = 'border-slate-700 hover:border-slate-600';
  if (validationError) borderColor = 'border-red-500/50 bg-red-900/10';
  else if (validationWarning) borderColor = 'border-orange-500/50 bg-orange-900/10';
  else if (isSelected) borderColor = 'border-blue-500 bg-blue-900/20 ring-1 ring-blue-500/50';

  // Handle immediate slider change
  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = Number(e.target.value);
      setLocalY(val); // Immediate UI update
  };

  // Commit change to parent on mouse up / blur
  const handleCommitChange = () => {
      const clamped = Math.max(50, Math.min(localY, maxHeight - 50));
      if (clamped !== shelf.y) {
          onUpdate({ ...shelf, y: clamped });
      }
  };

  // Calculated shelf dimensions (Cabinet Width - 2*16mm body, Depth - 20mm inset)
  const actualWidth = cabinetWidth - 32;
  const actualDepth = cabinetDepth - 20;

  return (
    <div 
        onClick={onSelect}
        className={`bg-[#222] rounded-lg border transition-all duration-300 cursor-pointer ${borderColor}`}
    >
      
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          <span className={`w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold shadow-sm ${isSelected ? 'bg-blue-600 text-white' : 'bg-slate-700 text-white'}`}>
            {index + 1}
          </span>
          <div className="flex flex-col">
              <span className="text-xs font-bold text-slate-200 leading-none">Полка 16мм</span>
              <span className="text-[9px] text-slate-500">{material}</span>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1 text-[10px] ${statusColor} bg-black/20 px-2 py-0.5 rounded font-medium`}>
                <StatusIcon size={10} />
                <span>{validationError ? 'ОШИБКА' : validationWarning ? 'WARN' : 'OK'}</span>
            </div>

            {isConfirmingDelete ? (
                <div className="flex items-center gap-1 animate-in fade-in slide-in-from-right-2 bg-slate-800 rounded p-0.5" onClick={e => e.stopPropagation()}>
                    <button onClick={onDelete} className="text-white bg-red-600 hover:bg-red-700 p-1 rounded" title="Подтвердить"><Trash2 size={12}/></button>
                    <button onClick={() => setIsConfirmingDelete(false)} className="text-slate-400 hover:bg-slate-700 p-1 rounded" title="Отмена"><X size={12}/></button>
                </div>
            ) : (
                <button onClick={(e) => { e.stopPropagation(); setIsConfirmingDelete(true); }} className="text-slate-500 hover:text-red-400 transition p-1 hover:bg-slate-700 rounded">
                    <Trash2 size={14} />
                </button>
            )}
        </div>
      </div>

      {/* Body */}
      <div className="p-3 space-y-3">
        
        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-2 text-[10px] text-slate-400">
            <div className="flex items-center gap-2 bg-black/20 p-2 rounded border border-white/5">
                <Ruler size={12} className="text-blue-400 shrink-0"/> 
                <div className="flex flex-col leading-none">
                    <span className="text-slate-300 font-mono">{actualWidth}x{actualDepth}</span>
                    <span className="text-[8px] opacity-50">Размер детали</span>
                </div>
            </div>
            <div className="flex items-center gap-2 bg-black/20 p-2 rounded border border-white/5">
                <Weight size={12} className="text-purple-400 shrink-0"/> 
                <div className="flex flex-col leading-none">
                    <span className="text-slate-300 font-mono">~{getLoadCapacity()}</span>
                    <span className="text-[8px] opacity-50">Нагрузка</span>
                </div>
            </div>
        </div>

        {/* Position Control */}
        <div className="bg-black/20 p-2 rounded border border-white/5" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between text-[10px] text-slate-500 mb-1.5">
                <span className="flex items-center gap-1.5 font-bold"><ArrowUp size={10}/> Позиция (Y)</span>
                <span className="font-mono text-blue-400 font-bold">{Math.round(localY)} мм</span>
            </div>
            <div className="flex items-center gap-3">
                <input 
                    type="range" 
                    min={50} 
                    max={maxHeight - 50} 
                    step={10}
                    value={localY} 
                    onChange={handleSliderChange}
                    onMouseUp={handleCommitChange}
                    onTouchEnd={handleCommitChange}
                    className={`flex-1 h-1.5 rounded-lg appearance-none cursor-pointer ${validationError ? 'bg-red-900 accent-red-500' : 'bg-slate-600 accent-blue-500'}`}
                />
                <button 
                    className="p-1 text-slate-500 hover:text-white bg-slate-700 rounded"
                    title="Точный ввод"
                    onClick={() => {
                        const val = prompt("Введите точную высоту (мм):", localY.toString());
                        if (val && !isNaN(+val)) {
                            const numVal = +val;
                            setLocalY(numVal);
                            onUpdate({ ...shelf, y: numVal });
                        }
                    }}
                >
                    <Settings2 size={12}/>
                </button>
            </div>
        </div>

        {/* Validation Message */}
        {(validationError || validationWarning) && (
            <div className={`text-[10px] px-2 py-2 rounded flex items-start gap-2 leading-relaxed border ${validationError ? 'text-red-200 bg-red-500/20 border-red-500/30' : 'text-orange-200 bg-orange-500/20 border-orange-500/30'}`}>
                <div className="mt-0.5 shrink-0"><StatusIcon size={12}/></div>
                <div>{validationError || validationWarning}</div>
            </div>
        )}

      </div>
    </div>
  );
};
