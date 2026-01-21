import React from 'react';
import { ChevronUp, ChevronDown, Maximize2, Minimize2, Eye, EyeOff } from 'lucide-react';

interface StatusBarProps {
  zoom: number;
  onZoomChange: (zoom: number) => void;
  gridSize: number;
  onGridChange: (size: number) => void;
  showGrid: boolean;
  onGridToggle: () => void;
  selectedCount: number;
  panelCount: number;
  currentMode: string;
  fps?: number;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  zoom,
  onZoomChange,
  gridSize,
  onGridChange,
  showGrid,
  onGridToggle,
  selectedCount,
  panelCount,
  currentMode,
  fps = 60
}) => {
  const handleZoomIn = () => onZoomChange(Math.min(200, zoom + 10));
  const handleZoomOut = () => onZoomChange(Math.max(10, zoom - 10));
  const handleZoomReset = () => onZoomChange(100);

  return (
    <div className="bg-slate-800 border-t border-slate-700 text-slate-300 text-xs h-10 flex items-center px-4 gap-6 shadow-md">
      {/* Left - File Info */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Режим:</span>
          <span className="font-mono text-blue-400">{currentMode}</span>
        </div>
        
        <div className="border-l border-slate-600 pl-4 flex items-center gap-2">
          <span className="text-slate-400">Панелей:</span>
          <span className="font-mono text-green-400">{panelCount}</span>
        </div>
        
        {selectedCount > 0 && (
          <div className="border-l border-slate-600 pl-4 flex items-center gap-2">
            <span className="text-slate-400">Выбрано:</span>
            <span className="font-mono text-yellow-400">{selectedCount}</span>
          </div>
        )}
      </div>

      {/* Center - Grid & Zoom */}
      <div className="flex-1 border-l border-r border-slate-600 px-4 flex items-center justify-center gap-4">
        {/* Grid Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={onGridToggle}
            className="p-1 hover:bg-slate-700 rounded transition-colors"
            title={showGrid ? 'Скрыть сетку' : 'Показать сетку'}
          >
            {showGrid ? <Eye size={14} /> : <EyeOff size={14} />}
          </button>
          
          <select
            value={gridSize}
            onChange={(e) => onGridChange(Number(e.target.value))}
            className="bg-slate-700 text-slate-300 rounded px-2 py-1 text-xs border border-slate-600 hover:border-slate-500 cursor-pointer"
          >
            <option value={10}>10 мм</option>
            <option value={25}>25 мм</option>
            <option value={50}>50 мм</option>
            <option value={100}>100 мм</option>
            <option value={250}>250 мм</option>
            <option value={500}>500 мм</option>
          </select>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-2 bg-slate-700 rounded px-2 py-1">
          <button
            onClick={handleZoomOut}
            className="p-0.5 hover:bg-slate-600 rounded transition-colors"
            title="Уменьшить масштаб"
          >
            <ChevronDown size={14} />
          </button>
          
          <button
            onClick={handleZoomReset}
            className="px-2 font-mono cursor-default hover:text-blue-400 transition-colors"
            title="Сбросить масштаб"
          >
            {zoom}%
          </button>
          
          <button
            onClick={handleZoomIn}
            className="p-0.5 hover:bg-slate-600 rounded transition-colors"
            title="Увеличить масштаб"
          >
            <ChevronUp size={14} />
          </button>
        </div>
      </div>

      {/* Right - Performance Info */}
      <div className="flex items-center gap-4">
        {fps && (
          <div className="flex items-center gap-2">
            <span className="text-slate-400">FPS:</span>
            <span className={`font-mono ${fps > 50 ? 'text-green-400' : fps > 30 ? 'text-yellow-400' : 'text-red-400'}`}>
              {fps}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
