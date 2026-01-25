
import React, { useState } from 'react';
import { useProjectStore } from '../store/projectStore';
import { HardwarePositions } from '../services/HardwarePositions';
import { Hardware } from '../types';
import { Settings, Plus, Trash2, Crosshair, Grid3X3, MousePointer2 } from 'lucide-react';

interface HardwarePanelProps {
    panelId: string;
}

export const HardwarePanel: React.FC<HardwarePanelProps> = ({ panelId }) => {
    const { panels, updatePanel } = useProjectStore();
    const panel = panels.find(p => p.id === panelId);
    const [handleSpacing, setHandleSpacing] = useState(128);

    if (!panel) return <div className="text-slate-500 p-4">Выберите деталь</div>;

    const addHinges = () => {
        const hinges = HardwarePositions.calculateHinges(panel);
        updatePanel(panel.id, { hardware: [...(panel.hardware || []), ...hinges] });
    };

    const addSystem32 = () => {
        const pins = HardwarePositions.calculateSystem32(panel);
        updatePanel(panel.id, { hardware: [...(panel.hardware || []), ...pins] });
    };

    const addHandle = () => {
        const handleHoles = HardwarePositions.calculateHandle(panel, handleSpacing);
        // Remove existing handles to prevent duplicates
        const cleanHardware = (panel.hardware || []).filter(h => h.type !== 'handle');
        updatePanel(panel.id, { hardware: [...cleanHardware, ...handleHoles] });
    };

    const removeHardware = (id: string) => {
        updatePanel(panel.id, { hardware: panel.hardware.filter(h => h.id !== id) });
    };

    const updateCoordinate = (id: string, axis: 'x' | 'y', value: number) => {
        const newHardware = panel.hardware.map(h => {
            if (h.id === id) {
                return { ...h, [axis]: value };
            }
            return h;
        });
        updatePanel(panel.id, { hardware: newHardware });
    };

    return (
        <div className="space-y-6">
            {/* Template Actions */}
            <div className="grid grid-cols-2 gap-2">
                <button onClick={addHinges} className="p-3 bg-slate-800 hover:bg-slate-700 rounded border border-slate-700 flex flex-col items-center gap-1 transition">
                    <div className="p-1.5 bg-blue-900/30 rounded text-blue-400"><Settings size={16}/></div>
                    <span className="text-[10px] font-bold text-white">Петли Blum</span>
                    <span className="text-[9px] text-slate-500">Стандарт d35</span>
                </button>
                <button onClick={addSystem32} className="p-3 bg-slate-800 hover:bg-slate-700 rounded border border-slate-700 flex flex-col items-center gap-1 transition">
                    <div className="p-1.5 bg-green-900/30 rounded text-green-400"><Grid3X3 size={16}/></div>
                    <span className="text-[10px] font-bold text-white">System 32</span>
                    <span className="text-[9px] text-slate-500">Полкодержатели</span>
                </button>
            </div>

            {/* Handle Config */}
            <div className="bg-slate-800 p-3 rounded border border-slate-700">
                <label className="text-[10px] font-bold text-slate-500 uppercase mb-2 block">Установка Ручки</label>
                <div className="flex gap-2">
                    <select 
                        value={handleSpacing} 
                        onChange={(e) => setHandleSpacing(Number(e.target.value))}
                        className="bg-slate-900 border border-slate-600 rounded text-xs text-white p-1.5 flex-1 outline-none focus:border-blue-500"
                    >
                        <option value={96}>96 мм</option>
                        <option value={128}>128 мм</option>
                        <option value={160}>160 мм</option>
                        <option value={192}>192 мм</option>
                    </select>
                    <button onClick={addHandle} className="bg-blue-600 hover:bg-blue-700 text-white px-3 rounded text-xs font-bold transition flex items-center gap-1">
                        <Plus size={14}/> Добавить
                    </button>
                </div>
            </div>

            {/* Drill List */}
            <div className="border-t border-slate-700 pt-4">
                <div className="flex justify-between items-center mb-2">
                    <h3 className="text-xs font-bold text-white flex items-center gap-2">
                        <Crosshair size={14} className="text-red-500"/> Карта сверления
                    </h3>
                    <span className="text-[10px] text-slate-500">{panel.hardware.length} отв.</span>
                </div>
                
                <div className="space-y-1 max-h-60 overflow-y-auto pr-1 no-scrollbar">
                    {panel.hardware.length === 0 && <div className="text-center text-slate-600 text-xs py-4">Нет отверстий</div>}
                    
                    {panel.hardware.map((hw, i) => (
                        <div key={hw.id} className="flex items-center gap-2 p-2 bg-slate-900 rounded border border-slate-800 text-xs group">
                            <span className="text-slate-500 w-4 text-[10px]">{i+1}</span>
                            <div className="flex-1 min-w-0">
                                <div className="truncate font-medium text-slate-300">{hw.name}</div>
                                <div className="text-[9px] text-slate-500">⌀{hw.diameter} x {hw.depth}мм</div>
                            </div>
                            
                            {/* Editable Coordinates */}
                            <div className="flex gap-1 items-center">
                                <span className="text-[9px] text-slate-600">X</span>
                                <input 
                                    type="number" 
                                    value={Math.round(hw.x)} 
                                    onChange={(e) => updateCoordinate(hw.id, 'x', Number(e.target.value))}
                                    className="w-10 bg-slate-800 border border-slate-700 rounded px-1 text-center text-slate-200 focus:border-blue-500 outline-none"
                                />
                                <span className="text-[9px] text-slate-600">Y</span>
                                <input 
                                    type="number" 
                                    value={Math.round(hw.y)} 
                                    onChange={(e) => updateCoordinate(hw.id, 'y', Number(e.target.value))}
                                    className="w-10 bg-slate-800 border border-slate-700 rounded px-1 text-center text-slate-200 focus:border-blue-500 outline-none"
                                />
                            </div>

                            <button onClick={() => removeHardware(hw.id)} className="text-slate-600 hover:text-red-500 p-1 transition opacity-0 group-hover:opacity-100">
                                <Trash2 size={12}/>
                            </button>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};
