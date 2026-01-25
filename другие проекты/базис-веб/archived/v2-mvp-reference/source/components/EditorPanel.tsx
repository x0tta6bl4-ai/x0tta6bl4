
import React, { useState, useEffect, useMemo } from 'react';
import { useProjectStore } from '../store/projectStore';
import { Material, Hardware, EdgeThickness, Panel, Groove } from '../types';
import { Trash2, Copy, Settings2, Box, CircleDot, Hammer, ListTree, SlidersHorizontal, Search, Eye, EyeOff, Layers, RotateCw, ScanLine, Wrench, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Lightbulb, PanelTop, Anchor, AlignVerticalSpaceAround, Maximize2, PenTool, Target } from 'lucide-react';
import PanelDrawing from './PanelDrawing';
import { HardwarePanel } from './HardwarePanel';

interface EditorPanelProps {
  materialLibrary: Material[];
  isDrawingMode?: boolean;
  onToggleView?: () => void;
}

const EditorPanel: React.FC<EditorPanelProps> = ({ materialLibrary, isDrawingMode, onToggleView }) => {
  const { panels, selectedPanelId, updatePanel, deletePanel, duplicatePanel, selectPanel } = useProjectStore();
  
  // Tabs: 'structure' (list of items) vs 'properties' (selected item details)
  const [activeTab, setActiveTab] = useState<'structure' | 'properties'>('structure');
  
  // Property Sub-tabs: Renamed and reorganized
  const [editTab, setEditTab] = useState<'main' | 'edge' | 'drilling' | 'hardware'>('main');
  const [searchTerm, setSearchTerm] = useState('');

  // Sync tab with selection
  useEffect(() => {
      if (selectedPanelId) {
          setActiveTab('properties');
      } else {
          setActiveTab('structure');
      }
  }, [selectedPanelId]);

  const selectedPanel = panels.find(p => p.id === selectedPanelId);

  // --- STRUCTURE VIEW HELPERS ---
  const filteredPanels = useMemo(() => {
      return panels.filter(p => 
          p.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
  }, [panels, searchTerm]);

  // Grouping by Layer (Simple aggregation)
  const groupedPanels = useMemo(() => {
      const groups: Record<string, Panel[]> = {};
      filteredPanels.forEach(p => {
          const groupName = p.layer === 'body' ? 'Корпус' :
                            p.layer === 'facade' ? 'Фасады' :
                            p.layer === 'shelves' ? 'Полки' : 
                            p.layer === 'back' ? 'Задняя стенка' : 'Фурнитура';
          if (!groups[groupName]) groups[groupName] = [];
          groups[groupName].push(p);
      });
      return groups;
  }, [filteredPanels]);

  const toggleVisibility = (e: React.MouseEvent, id: string, current: boolean) => {
      e.stopPropagation();
      updatePanel(id, { visible: !current });
  };

  const updateGroove = (changes: Partial<Groove>) => {
      if (!selectedPanel) return;
      const currentGroove = selectedPanel.groove || { enabled: false, side: 'top', width: 4, depth: 10, offset: 16 };
      updatePanel(selectedPanel.id, { groove: { ...currentGroove, ...changes } });
  };

  const inputClass = "w-full mt-1.5 p-2 border border-slate-700 rounded-md text-xs bg-slate-800 text-slate-100 focus:ring-2 focus:ring-blue-500 outline-none transition font-mono";
  const labelClass = "text-[10px] font-bold text-slate-500 uppercase tracking-wider";

  // --- RENDER ---
  return (
    <div className="w-full h-full bg-[#1e1e1e] flex flex-col shadow-2xl z-20 text-slate-300 no-scrollbar">
      
      {/* TOP TABS: STRUCTURE vs PROPERTIES */}
      <div className="flex border-b border-slate-700 bg-[#252526] shrink-0">
          <button 
            onClick={() => setActiveTab('structure')}
            className={`flex-1 py-3 text-[10px] md:text-xs font-bold uppercase flex items-center justify-center gap-2 transition ${activeTab === 'structure' ? 'text-blue-400 bg-slate-800 border-b-2 border-blue-500' : 'text-slate-500 hover:text-white'}`}
          >
              <ListTree size={16}/> Структура
          </button>
          <button 
            onClick={() => { if(selectedPanel) setActiveTab('properties'); }}
            disabled={!selectedPanel}
            className={`flex-1 py-3 text-[10px] md:text-xs font-bold uppercase flex items-center justify-center gap-2 transition ${activeTab === 'properties' ? 'text-blue-400 bg-slate-800 border-b-2 border-blue-500' : 'text-slate-500 hover:text-white disabled:opacity-30'}`}
          >
              <SlidersHorizontal size={16}/> Свойства
          </button>
      </div>

      {/* CONTENT AREA */}
      <div className="flex-1 overflow-hidden relative bg-[#1e1e1e]">
          
          {/* === STRUCTURE VIEW === */}
          {activeTab === 'structure' && (
              <div className="h-full flex flex-col animate-in slide-in-from-left-2 fade-in duration-300">
                  {/* Search Bar */}
                  <div className="p-3 border-b border-slate-700 bg-[#252526]">
                      <div className="relative">
                          <Search className="absolute left-2 top-2 text-slate-500" size={14}/>
                          <input 
                            type="text" 
                            placeholder="Поиск детали..." 
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full bg-[#1a1a1a] border border-slate-600 rounded pl-8 pr-2 py-1.5 text-xs text-white focus:border-blue-500 focus:outline-none"
                          />
                      </div>
                      <div className="flex justify-between mt-2 text-[10px] text-slate-500 px-1">
                          <span>Всего деталей: {panels.length}</span>
                          <span>Выбрано: {selectedPanelId ? 1 : 0}</span>
                      </div>
                  </div>

                  {/* Tree List */}
                  <div className="flex-1 overflow-y-auto p-2 no-scrollbar space-y-4">
                      {Object.keys(groupedPanels).length === 0 && (
                          <div className="text-center text-slate-500 py-10 text-xs">Нет деталей в проекте</div>
                      )}

                      {(Object.entries(groupedPanels) as [string, Panel[]][]).map(([groupName, groupItems]) => (
                          <div key={groupName}>
                              <div className="text-[10px] font-bold text-blue-500 uppercase px-2 mb-1 flex items-center gap-2">
                                  <Layers size={12}/> {groupName}
                              </div>
                              <div className="space-y-0.5">
                                  {groupItems.map(p => (
                                      <div 
                                        key={p.id}
                                        onClick={() => selectPanel(p.id)}
                                        role="button"
                                        aria-label={`Выбрать деталь ${p.name}`}
                                        aria-selected={p.id === selectedPanelId}
                                        className={`flex items-center gap-2 p-2 rounded cursor-pointer border border-transparent transition-all duration-200 ease-out group 
                                            ${p.id === selectedPanelId 
                                                ? 'bg-blue-600 text-white shadow-[0_4px_12px_rgba(37,99,235,0.5)] scale-[1.02] z-10 relative border-blue-500' 
                                                : 'hover:bg-slate-800 hover:border-slate-700 text-slate-400 hover:scale-[1.02] hover:text-slate-200 hover:shadow-sm'
                                            }`}
                                      >
                                          <Box size={14} className={p.id === selectedPanelId ? 'text-white' : 'text-slate-600'} aria-hidden="true"/>
                                          <div className="flex-1 min-w-0">
                                              <div className={`text-xs font-medium truncate ${p.id === selectedPanelId ? 'text-white' : 'text-slate-300'}`}>{p.name}</div>
                                              <div className={`text-[10px] font-mono ${p.id === selectedPanelId ? 'text-blue-200' : 'text-slate-600'}`}>{p.width} x {p.height}</div>
                                          </div>
                                          <button 
                                            onClick={(e) => toggleVisibility(e, p.id, p.visible)}
                                            aria-label={p.visible ? "Скрыть деталь" : "Показать деталь"}
                                            className={`p-1 rounded hover:bg-black/20 ${p.visible ? '' : 'text-slate-600'}`}
                                          >
                                              {p.visible ? <Eye size={14}/> : <EyeOff size={14}/>}
                                          </button>
                                      </div>
                                  ))}
                              </div>
                          </div>
                      ))}
                  </div>
              </div>
          )}

          {/* === PROPERTIES VIEW === */}
          {activeTab === 'properties' && selectedPanel && (
              <div className="h-full flex flex-col animate-in slide-in-from-right-2 fade-in duration-300">
                  {/* Panel Header */}
                  <div className="p-4 bg-[#252526] border-b border-slate-700 shrink-0">
                      <div className="flex justify-between items-center mb-4">
                          <input 
                            type="text" 
                            aria-label="Название детали"
                            value={selectedPanel.name} 
                            onChange={e => updatePanel(selectedPanel.id, { name: e.target.value })}
                            className="bg-transparent font-bold text-white border-b border-transparent hover:border-slate-500 focus:border-blue-500 focus:outline-none p-0 text-sm w-40 truncate transition-colors"
                          />
                          <div className="flex gap-1">
                              <button onClick={() => duplicatePanel(selectedPanel.id)} aria-label="Дублировать деталь" className="p-2 hover:bg-slate-700 rounded text-slate-400" title="Дублировать"><Copy size={14}/></button>
                              <button onClick={() => deletePanel(selectedPanel.id)} aria-label="Удалить деталь" className="p-2 hover:bg-red-900/30 rounded text-red-500" title="Удалить"><Trash2 size={14}/></button>
                          </div>
                      </div>
                      <div className="h-24 bg-slate-900 rounded-lg border border-slate-800 overflow-hidden flex items-center justify-center relative group">
                          <div className="absolute inset-0 opacity-50 pointer-events-none">
                              <PanelDrawing panel={selectedPanel} width={300} height={128} detailed={false} />
                          </div>
                          
                          {/* VIEW TOGGLE BUTTON */}
                          {onToggleView && (
                              <button 
                                onClick={onToggleView}
                                className={`absolute bottom-2 right-2 px-3 py-1.5 rounded-full shadow-lg font-bold text-[10px] flex items-center gap-1.5 transition-all transform hover:scale-105 active:scale-95
                                    ${isDrawingMode ? 'bg-slate-700 text-white hover:bg-slate-600' : 'bg-blue-600 text-white hover:bg-blue-500'}`}
                              >
                                  {isDrawingMode ? <Box size={14}/> : <PenTool size={14}/>}
                                  {isDrawingMode ? '3D Вид' : 'Чертеж'}
                              </button>
                          )}
                      </div>
                  </div>

                  {/* Sub-Tabs */}
                  <div className="flex border-b border-slate-700 bg-[#252526] shrink-0 overflow-x-auto no-scrollbar">
                      <button onClick={() => setEditTab('main')} className={`flex-1 min-w-[70px] py-2 text-[9px] font-bold uppercase transition ${editTab === 'main' ? 'text-blue-400 border-b border-blue-500' : 'text-slate-500 hover:text-slate-300'}`}>Основные</button>
                      <button onClick={() => setEditTab('edge')} className={`flex-1 min-w-[70px] py-2 text-[9px] font-bold uppercase transition ${editTab === 'edge' ? 'text-blue-400 border-b border-blue-500' : 'text-slate-500 hover:text-slate-300'}`}>Кромка</button>
                      <button onClick={() => setEditTab('drilling')} className={`flex-1 min-w-[70px] py-2 text-[9px] font-bold uppercase transition ${editTab === 'drilling' ? 'text-blue-400 border-b border-blue-500' : 'text-slate-500 hover:text-slate-300'}`}>Присадка</button>
                      <button onClick={() => setEditTab('hardware')} className={`flex-1 min-w-[70px] py-2 text-[9px] font-bold uppercase transition ${editTab === 'hardware' ? 'text-blue-400 border-b border-blue-500' : 'text-slate-500 hover:text-slate-300'}`}>Фурнитура</button>
                  </div>

                  {/* Edit Forms */}
                  <div className="flex-1 overflow-y-auto p-4 space-y-6 no-scrollbar">
                      {/* 1. BASIC PARAMETERS */}
                      {editTab === 'main' && (
                          <div className="space-y-4">
                              <div className="grid grid-cols-1 xs:grid-cols-2 gap-3">
                                  <div><label className={labelClass}>Длина (L)</label><input type="number" value={selectedPanel.width} onChange={e => updatePanel(selectedPanel.id, {width: +e.target.value})} className={inputClass} /></div>
                                  <div><label className={labelClass}>Ширина (W)</label><input type="number" value={selectedPanel.height} onChange={e => updatePanel(selectedPanel.id, {height: +e.target.value})} className={inputClass} /></div>
                              </div>
                              <div>
                                  <label className={labelClass}>Материал (ЛДСП)</label>
                                  <select 
                                    value={selectedPanel.materialId} 
                                    onChange={e => {
                                        const mat = materialLibrary.find(m => m.id === e.target.value);
                                        if (mat) updatePanel(selectedPanel.id, { materialId: mat.id, color: mat.color, texture: mat.texture, depth: mat.thickness });
                                    }}
                                    className={inputClass}
                                  >
                                      {materialLibrary.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                                  </select>
                              </div>
                              <div className="flex items-center justify-between p-3 bg-slate-800 rounded border border-slate-700 mt-2 hover:bg-slate-750 transition cursor-pointer"
                                   onClick={() => updatePanel(selectedPanel.id, { textureRotation: selectedPanel.textureRotation === 0 ? 90 : 0 })}>
                                  <span className="text-[10px] font-bold text-slate-400 flex items-center gap-2"><ScanLine size={14}/> НАПРАВЛЕНИЕ ТЕКСТУРЫ</span>
                                  <div className={`flex items-center gap-2 text-xs px-3 py-1 rounded transition border ${selectedPanel.textureRotation === 90 ? 'bg-blue-900/30 text-blue-400 border-blue-500/50' : 'bg-slate-700 text-slate-300 border-slate-600'}`}>
                                      <RotateCw size={14} className={selectedPanel.textureRotation === 90 ? 'rotate-90' : ''}/> 
                                      {selectedPanel.textureRotation}° (Вдоль {selectedPanel.textureRotation === 90 ? 'W' : 'L'})
                                  </div>
                              </div>
                              <div className="grid grid-cols-3 gap-2 border-t border-slate-800 pt-4">
                                  <div><label className={labelClass}>X</label><input type="number" value={Math.round(selectedPanel.x)} onChange={e => updatePanel(selectedPanel.id, {x: +e.target.value})} className={inputClass} /></div>
                                  <div><label className={labelClass}>Y</label><input type="number" value={Math.round(selectedPanel.y)} onChange={e => updatePanel(selectedPanel.id, {y: +e.target.value})} className={inputClass} /></div>
                                  <div><label className={labelClass}>Z</label><input type="number" value={Math.round(selectedPanel.z)} onChange={e => updatePanel(selectedPanel.id, {z: +e.target.value})} className={inputClass} /></div>
                              </div>
                          </div>
                      )}

                      {/* 2. EDGING */}
                      {editTab === 'edge' && (
                          <div className="space-y-3">
                              {(['top', 'bottom', 'left', 'right'] as const).map(side => (
                                  <div key={side} className="flex items-center justify-between p-2 bg-slate-800 rounded border border-slate-700">
                                      <span className="text-[10px] font-bold uppercase text-slate-400 w-12">{side}</span>
                                      <select 
                                        value={selectedPanel.edging[side]}
                                        onChange={e => updatePanel(selectedPanel.id, { edging: { ...selectedPanel.edging, [side]: e.target.value as EdgeThickness } })}
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
                                  <p className="text-[10px] text-blue-300 leading-relaxed">Кромка 2.0мм автоматически уменьшает пильный размер детали на 2мм с каждой стороны.</p>
                              </div>
                          </div>
                      )}

                      {/* 3. DRILLING (GROOVE) */}
                      {editTab === 'drilling' && (
                          <div className="space-y-6">
                              {/* Visual Groove Editor */}
                              <div className="space-y-2">
                                  <label className={labelClass}>Паз (Четверть)</label>
                                  
                                  <div className="flex items-center justify-between bg-slate-800 p-3 rounded-t border border-slate-700">
                                      <span className="text-xs font-bold text-white flex items-center gap-2"><ScanLine size={16}/> Активность</span>
                                      <div className="flex items-center gap-2">
                                          <span className="text-[10px] text-slate-400">{selectedPanel.groove?.enabled ? 'Включен' : 'Выключен'}</span>
                                          <input 
                                            type="checkbox" 
                                            checked={selectedPanel.groove?.enabled || false}
                                            onChange={e => updateGroove({ enabled: e.target.checked })}
                                            className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-blue-600 focus:ring-blue-500"
                                          />
                                      </div>
                                  </div>

                                  {(selectedPanel.groove?.enabled) && (
                                      <div className="animate-in slide-in-from-top-2 p-3 bg-slate-800/50 rounded-b border-x border-b border-slate-700/50">
                                          {/* Visual Selector */}
                                          <div className="flex justify-center mb-4">
                                              <div className="relative w-32 h-24 bg-slate-700/50 border border-slate-600 rounded flex items-center justify-center">
                                                  <div className="text-[9px] text-slate-500">ДЕТАЛЬ</div>
                                                  
                                                  {/* Buttons positioned absolutely */}
                                                  <button onClick={() => updateGroove({ side: 'top' })} aria-label="Паз сверху" className={`absolute -top-3 left-1/2 -translate-x-1/2 p-1 rounded-full border shadow-sm ${selectedPanel.groove.side === 'top' ? 'bg-blue-500 border-blue-400 text-white' : 'bg-slate-800 border-slate-600 text-slate-400 hover:bg-slate-700'}`}><ArrowUp size={12}/></button>
                                                  <button onClick={() => updateGroove({ side: 'bottom' })} aria-label="Паз снизу" className={`absolute -bottom-3 left-1/2 -translate-x-1/2 p-1 rounded-full border shadow-sm ${selectedPanel.groove.side === 'bottom' ? 'bg-blue-500 border-blue-400 text-white' : 'bg-slate-800 border-slate-600 text-slate-400 hover:bg-slate-700'}`}><ArrowDown size={12}/></button>
                                                  <button onClick={() => updateGroove({ side: 'left' })} aria-label="Паз слева" className={`absolute top-1/2 -left-3 -translate-y-1/2 p-1 rounded-full border shadow-sm ${selectedPanel.groove.side === 'left' ? 'bg-blue-500 border-blue-400 text-white' : 'bg-slate-800 border-slate-600 text-slate-400 hover:bg-slate-700'}`}><ArrowLeft size={12}/></button>
                                                  <button onClick={() => updateGroove({ side: 'right' })} aria-label="Паз справа" className={`absolute top-1/2 -right-3 -translate-y-1/2 p-1 rounded-full border shadow-sm ${selectedPanel.groove.side === 'right' ? 'bg-blue-500 border-blue-400 text-white' : 'bg-slate-800 border-slate-600 text-slate-400 hover:bg-slate-700'}`}><ArrowRight size={12}/></button>
                                                  
                                                  {/* Active Indicator Line inside */}
                                                  {selectedPanel.groove.side === 'top' && <div className="absolute top-1 left-2 right-2 h-1 bg-blue-500/50 rounded-full animate-pulse"></div>}
                                                  {selectedPanel.groove.side === 'bottom' && <div className="absolute bottom-1 left-2 right-2 h-1 bg-blue-500/50 rounded-full animate-pulse"></div>}
                                                  {selectedPanel.groove.side === 'left' && <div className="absolute top-2 bottom-2 left-1 w-1 bg-blue-500/50 rounded-full animate-pulse"></div>}
                                                  {selectedPanel.groove.side === 'right' && <div className="absolute top-2 bottom-2 right-1 w-1 bg-blue-500/50 rounded-full animate-pulse"></div>}
                                              </div>
                                          </div>

                                          <div className="grid grid-cols-3 gap-2 mb-4">
                                              <div><label className={labelClass}>Ширина</label><input type="number" value={selectedPanel.groove.width} onChange={e => updateGroove({width: +e.target.value})} className={inputClass} /></div>
                                              <div><label className={labelClass}>Глубина</label><input type="number" value={selectedPanel.groove.depth} onChange={e => updateGroove({depth: +e.target.value})} className={inputClass} /></div>
                                              <div><label className={labelClass}>Отступ</label><input type="number" value={selectedPanel.groove.offset} onChange={e => updateGroove({offset: +e.target.value})} className={inputClass} /></div>
                                          </div>

                                          {/* Presets */}
                                          <div className="flex gap-2 border-t border-slate-700 pt-3">
                                              <button onClick={() => updateGroove({ width: 4, depth: 10, offset: 16 })} className="flex-1 py-1.5 px-2 bg-slate-700 hover:bg-slate-600 rounded text-[9px] text-white flex items-center justify-center gap-1">
                                                  <PanelTop size={12}/> Под ХДФ
                                              </button>
                                              <button onClick={() => updateGroove({ width: 16, depth: 8, offset: 10 })} className="flex-1 py-1.5 px-2 bg-slate-700 hover:bg-slate-600 rounded text-[9px] text-white flex items-center justify-center gap-1">
                                                  <Lightbulb size={12}/> Под LED
                                              </button>
                                          </div>
                                      </div>
                                  )}
                              </div>
                          </div>
                      )}

                      {/* 4. HARDWARE CALCULATOR */}
                      {editTab === 'hardware' && (
                          <HardwarePanel panelId={selectedPanel.id} />
                      )}
                  </div>
              </div>
          )}
      </div>
    </div>
  );
};

export default EditorPanel;
