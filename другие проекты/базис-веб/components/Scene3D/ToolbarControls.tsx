import React from 'react';
import { Move, RefreshCw, Box, Layers, Eye, Grid3X3, Move3d } from 'lucide-react';

interface ToolbarControlsProps {
  visualStyle: 'realistic' | 'wireframe' | 'xray';
  gizmoMode: 'translate' | 'rotate';
  showGrid: boolean;
  showAxes: boolean;
  enabledAxes: { x: boolean; y: boolean; z: boolean };
  onVisualStyleChange: (style: 'realistic' | 'wireframe' | 'xray') => void;
  onGizmoModeChange: (mode: 'translate' | 'rotate') => void;
  onShowGridChange: (show: boolean) => void;
  onShowAxesChange: (show: boolean) => void;
  onToggleAxis: (axis: 'x' | 'y' | 'z') => void;
}

const ToolbarControls: React.FC<ToolbarControlsProps> = ({
  visualStyle,
  gizmoMode,
  showGrid,
  showAxes,
  enabledAxes,
  onVisualStyleChange,
  onGizmoModeChange,
  onShowGridChange,
  onShowAxesChange,
  onToggleAxis,
}) => {
  return (
    <div className="absolute top-16 left-4 flex flex-col gap-3 z-40">
      <div className="bg-[#1a1a1a]/90 backdrop-blur border border-slate-700 p-1 rounded-lg flex flex-col gap-1 shadow-xl">
        <button
          onClick={() => onVisualStyleChange('realistic')}
          className={`p-2 rounded transition ${visualStyle === 'realistic' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}
          title="Реалистичный"
        >
          <Box size={18} />
        </button>
        <button
          onClick={() => onVisualStyleChange('wireframe')}
          className={`p-2 rounded transition ${visualStyle === 'wireframe' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}
          title="Каркас"
        >
          <Layers size={18} />
        </button>
        <button
          onClick={() => onVisualStyleChange('xray')}
          className={`p-2 rounded transition ${visualStyle === 'xray' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}
          title="Рентген"
        >
          <Eye size={18} />
        </button>
      </div>

      <div className="bg-[#1a1a1a]/90 backdrop-blur border border-slate-700 p-1 rounded-lg flex flex-col gap-1 shadow-xl">
        <button
          onClick={() => onGizmoModeChange('translate')}
          className={`p-2 rounded transition ${gizmoMode === 'translate' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}
          title="Перемещение"
        >
          <Move size={18} />
        </button>
        <button
          onClick={() => onGizmoModeChange('rotate')}
          className={`p-2 rounded transition ${gizmoMode === 'rotate' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}
          title="Вращение"
        >
          <RefreshCw size={18} />
        </button>
        <div className="h-px bg-slate-700 my-1 mx-2"></div>
        <button
          onClick={() => onToggleAxis('x')}
          className={`text-[10px] font-bold p-1 rounded ${enabledAxes.x ? 'text-red-500 bg-red-500/10' : 'text-slate-600'}`}
        >
          X
        </button>
        <button
          onClick={() => onToggleAxis('y')}
          className={`text-[10px] font-bold p-1 rounded ${enabledAxes.y ? 'text-green-500 bg-green-500/10' : 'text-slate-600'}`}
        >
          Y
        </button>
        <button
          onClick={() => onToggleAxis('z')}
          className={`text-[10px] font-bold p-1 rounded ${enabledAxes.z ? 'text-blue-500 bg-blue-500/10' : 'text-slate-600'}`}
        >
          Z
        </button>
      </div>

      <div className="bg-[#1a1a1a]/90 backdrop-blur border border-slate-700 p-1 rounded-lg flex flex-col gap-1 shadow-xl">
        <button
          onClick={() => onShowGridChange(!showGrid)}
          className={`p-2 rounded transition ${showGrid ? 'text-blue-400 bg-blue-900/20' : 'text-slate-500'}`}
          title="Сетка"
        >
          <Grid3X3 size={18} />
        </button>
        <button
          onClick={() => onShowAxesChange(!showAxes)}
          className={`p-2 rounded transition ${showAxes ? 'text-blue-400 bg-blue-900/20' : 'text-slate-500'}`}
          title="Оси"
        >
          <Move3d size={18} />
        </button>
      </div>
    </div>
  );
};

export default ToolbarControls;
