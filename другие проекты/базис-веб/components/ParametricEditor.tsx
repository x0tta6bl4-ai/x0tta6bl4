import React, { useState, useCallback, useMemo } from 'react';
import { useProjectStore } from '../store/projectStore';
import { Panel } from '../types';
import { 
  Maximize2, Grid3X3, Lock, Unlock, RotateCcw, ZoomIn, ZoomOut,
  Sliders, Droplet, Copy
} from 'lucide-react';

interface ParametricEditorProps {
  selectedPanel: Panel | null;
}

const STANDARD_WIDTHS = [400, 600, 800, 1000, 1200, 1500, 1800, 2000];
const STANDARD_HEIGHTS = [400, 600, 800, 1000, 1200, 1500, 1800, 2000, 2500];
const STANDARD_DEPTHS = [300, 350, 400, 450, 500, 550, 600, 650];

const ParametricEditor: React.FC<ParametricEditorProps> = ({ selectedPanel }) => {
  const { updatePanel, panels } = useProjectStore();
  const [lockAspectRatio, setLockAspectRatio] = useState(false);
  const [aspectRatio, setAspectRatio] = useState(1);
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [gridStep, setGridStep] = useState(50);

  const handleDimensionChange = useCallback((dimension: 'width' | 'height' | 'depth', value: number) => {
    if (!selectedPanel) return;

    let newValue = value;
    if (snapToGrid) {
      newValue = Math.round(value / gridStep) * gridStep;
    }
    newValue = Math.max(10, Math.min(newValue, dimension === 'depth' ? 1000 : 3000));

    const updates: Partial<Panel> = { [dimension]: newValue };

    if (lockAspectRatio && (dimension === 'width' || dimension === 'height')) {
      if (dimension === 'width') {
        updates.height = Math.round((newValue / aspectRatio));
      } else {
        updates.width = Math.round((newValue * aspectRatio));
      }
    }

    updatePanel(selectedPanel.id, updates);
  }, [selectedPanel, lockAspectRatio, aspectRatio, snapToGrid, gridStep, updatePanel]);

  const handleLockAspect = useCallback(() => {
    if (selectedPanel && !lockAspectRatio) {
      setAspectRatio(selectedPanel.width / selectedPanel.height);
    }
    setLockAspectRatio(!lockAspectRatio);
  }, [selectedPanel, lockAspectRatio]);

  const handleApplyPreset = useCallback((dimension: 'width' | 'height' | 'depth', value: number) => {
    if (!selectedPanel) return;
    handleDimensionChange(dimension, value);
  }, [selectedPanel, handleDimensionChange]);

  const calculateArea = useMemo(() => {
    if (!selectedPanel) return 0;
    return (selectedPanel.width * selectedPanel.height) / 1000000;
  }, [selectedPanel]);

  const calculateVolume = useMemo(() => {
    if (!selectedPanel) return 0;
    return (selectedPanel.width * selectedPanel.height * selectedPanel.depth) / 1000000000;
  }, [selectedPanel]);

  if (!selectedPanel) {
    return (
      <div className="w-full h-full bg-[#1e1e1e] flex items-center justify-center text-slate-500 text-sm border-l border-slate-700">
        <Sliders size={24} className="mr-2" />
        Выберите деталь для редактирования
      </div>
    );
  }

  return (
    <div className="w-full h-full bg-[#1e1e1e] flex flex-col text-slate-300 border-l border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-slate-700 bg-[#252526] shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <Maximize2 size={18} className="text-blue-500" />
          <h2 className="text-sm font-bold uppercase tracking-wider">Параметры детали</h2>
        </div>
        <p className="text-xs text-slate-500 font-mono">{selectedPanel.name}</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        
        {/* Dimensions Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase text-blue-400">Размеры (мм)</h3>
            <button
              onClick={handleLockAspect}
              className={`p-1.5 rounded transition ${
                lockAspectRatio
                  ? 'bg-blue-600/30 text-blue-400'
                  : 'bg-slate-800 text-slate-500 hover:text-slate-300'
              }`}
              title={lockAspectRatio ? 'Пропорция заблокирована' : 'Заблокировать пропорцию'}
            >
              {lockAspectRatio ? <Lock size={14} /> : <Unlock size={14} />}
            </button>
          </div>

          {/* Width */}
          <div className="space-y-2">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Ширина</label>
            <div className="flex gap-2">
              <input
                type="range"
                min="50"
                max="3000"
                step={snapToGrid ? gridStep : 1}
                value={selectedPanel.width}
                onChange={(e) => handleDimensionChange('width', Number(e.target.value))}
                className="flex-1 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <input
                type="number"
                value={selectedPanel.width}
                onChange={(e) => handleDimensionChange('width', Number(e.target.value))}
                className="w-16 px-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div className="grid grid-cols-4 gap-1">
              {STANDARD_WIDTHS.map((w) => (
                <button
                  key={w}
                  onClick={() => handleApplyPreset('width', w)}
                  className={`text-[10px] py-1 rounded transition ${
                    selectedPanel.width === w
                      ? 'bg-blue-600 text-white font-bold'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  {w}
                </button>
              ))}
            </div>
          </div>

          {/* Height */}
          <div className="space-y-2">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Высота</label>
            <div className="flex gap-2">
              <input
                type="range"
                min="50"
                max="3000"
                step={snapToGrid ? gridStep : 1}
                value={selectedPanel.height}
                onChange={(e) => handleDimensionChange('height', Number(e.target.value))}
                className="flex-1 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <input
                type="number"
                value={selectedPanel.height}
                onChange={(e) => handleDimensionChange('height', Number(e.target.value))}
                className="w-16 px-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div className="grid grid-cols-4 gap-1">
              {STANDARD_HEIGHTS.map((h) => (
                <button
                  key={h}
                  onClick={() => handleApplyPreset('height', h)}
                  className={`text-[10px] py-1 rounded transition ${
                    selectedPanel.height === h
                      ? 'bg-blue-600 text-white font-bold'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  {h}
                </button>
              ))}
            </div>
          </div>

          {/* Depth */}
          <div className="space-y-2">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Глубина</label>
            <div className="flex gap-2">
              <input
                type="range"
                min="10"
                max="1000"
                step={snapToGrid ? gridStep : 1}
                value={selectedPanel.depth}
                onChange={(e) => handleDimensionChange('depth', Number(e.target.value))}
                className="flex-1 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <input
                type="number"
                value={selectedPanel.depth}
                onChange={(e) => handleDimensionChange('depth', Number(e.target.value))}
                className="w-16 px-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div className="grid grid-cols-4 gap-1">
              {STANDARD_DEPTHS.map((d) => (
                <button
                  key={d}
                  onClick={() => handleApplyPreset('depth', d)}
                  className={`text-[10px] py-1 rounded transition ${
                    selectedPanel.depth === d
                      ? 'bg-blue-600 text-white font-bold'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Position Section */}
        <div className="space-y-3 pt-2 border-t border-slate-700">
          <h3 className="text-xs font-bold uppercase text-blue-400">Позиция (мм)</h3>
          <div className="grid grid-cols-3 gap-2">
            {(['x', 'y', 'z'] as const).map((axis) => (
              <div key={axis} className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase block">{axis.toUpperCase()}</label>
                <input
                  type="number"
                  value={selectedPanel[axis]}
                  onChange={(e) => updatePanel(selectedPanel.id, { [axis]: Number(e.target.value) })}
                  className="w-full px-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded font-mono focus:border-blue-500 focus:outline-none"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Grid Settings */}
        <div className="space-y-3 pt-2 border-t border-slate-700">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={snapToGrid}
              onChange={(e) => setSnapToGrid(e.target.checked)}
              className="w-4 h-4 bg-slate-800 border border-slate-700 rounded cursor-pointer accent-blue-600"
            />
            <span className="text-xs font-bold text-slate-400 uppercase">Привязка к сетке</span>
          </label>
          {snapToGrid && (
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase block">Шаг сетки (мм)</label>
              <input
                type="number"
                value={gridStep}
                onChange={(e) => setGridStep(Math.max(1, Number(e.target.value)))}
                className="w-full px-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
          )}
        </div>

        {/* Statistics */}
        <div className="space-y-3 pt-2 border-t border-slate-700 bg-slate-900/30 p-3 rounded">
          <h3 className="text-xs font-bold uppercase text-slate-400">Параметры</h3>
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="flex items-center gap-2">
              <Droplet size={12} className="text-blue-400" />
              <span className="text-slate-500">Площадь:</span>
            </div>
            <div className="text-white font-mono">{calculateArea.toFixed(2)} м²</div>
            
            <div className="flex items-center gap-2">
              <Droplet size={12} className="text-cyan-400" />
              <span className="text-slate-500">Объем:</span>
            </div>
            <div className="text-white font-mono">{calculateVolume.toFixed(4)} м³</div>

            <div className="flex items-center gap-2">
              <Droplet size={12} className="text-purple-400" />
              <span className="text-slate-500">Периметр:</span>
            </div>
            <div className="text-white font-mono">{(2 * (selectedPanel.width + selectedPanel.height) / 1000).toFixed(2)} м</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ParametricEditor;
