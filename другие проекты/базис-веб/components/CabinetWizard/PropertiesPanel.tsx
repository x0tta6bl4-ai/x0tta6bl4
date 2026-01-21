import React from 'react';
import { MousePointer2, Settings, BoxSelect, StretchVertical, MonitorPlay } from 'lucide-react';
import { CabinetConfig, Section, CabinetItem, DoorType } from '../../types';
import { TabButton, VisualSelector } from './shared';
import { PanelBottom, Footprints, LayoutGrid, DoorOpen, GripHorizontal } from 'lucide-react';

interface PropertiesPanelProps {
  activeTab: 'global' | 'item';
  onTabChange: (tab: 'global' | 'item') => void;
  config: CabinetConfig;
  onConfigChange: (config: CabinetConfig) => void;
  sections: Section[];
  selectedItemId: string | null;
  selectedSectionId: number;
  onDistributeItems: () => void;
  onUpdateItem: (itemId: string, updates: Partial<CabinetItem>) => void;
  onGenerate: () => void;
}

export const PropertiesPanel: React.FC<PropertiesPanelProps> = ({
  activeTab,
  onTabChange,
  config,
  onConfigChange,
  sections,
  selectedItemId,
  selectedSectionId,
  onDistributeItems,
  onUpdateItem,
  onGenerate,
}) => {
  const selectedItem = sections.flatMap(s => s.items).find(i => i.id === selectedItemId);

  return (
    <div className="w-80 bg-[#252526] border-l border-[#333] flex flex-col z-20 shrink-0 shadow-2xl">
      {/* Tabs */}
      <div className="flex border-b border-[#333] bg-[#2a2a2b]">
        <TabButton
          active={activeTab === 'global'}
          onClick={() => onTabChange('global')}
          label="Параметры"
          icon={Settings}
        />
        <TabButton
          active={activeTab === 'item'}
          onClick={() => onTabChange('item')}
          label="Элемент"
          icon={BoxSelect}
        />
      </div>

      <div className="flex-1 overflow-y-auto p-5 no-scrollbar">
        {activeTab === 'global' ? (
          <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
            {/* Dimensions */}
            <div className="space-y-3">
              <label className="text-[10px] font-bold text-blue-500 uppercase tracking-wider block">
                Габариты изделия
              </label>
              <div className="grid grid-cols-3 gap-2">
                <div
                  className={`bg-[#1a1a1a] p-2 rounded border ${
                    !config.width || config.width <= 0 ? 'border-red-500/50' : 'border-[#333]'
                  }`}
                >
                  <label className="text-[9px] text-slate-500 block flex justify-between">
                    Ширина <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    value={config.width || ''}
                    onChange={e => onConfigChange({ ...config, width: +e.target.value })}
                    className="w-full bg-transparent text-sm font-bold text-white outline-none font-mono"
                  />
                </div>
                <div
                  className={`bg-[#1a1a1a] p-2 rounded border ${
                    !config.height || config.height <= 0 ? 'border-red-500/50' : 'border-[#333]'
                  }`}
                >
                  <label className="text-[9px] text-slate-500 block flex justify-between">
                    Высота <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    value={config.height || ''}
                    onChange={e => onConfigChange({ ...config, height: +e.target.value })}
                    className="w-full bg-transparent text-sm font-bold text-white outline-none font-mono"
                  />
                </div>
                <div
                  className={`bg-[#1a1a1a] p-2 rounded border ${
                    !config.depth || config.depth <= 0 ? 'border-red-500/50' : 'border-[#333]'
                  }`}
                >
                  <label className="text-[9px] text-slate-500 block flex justify-between">
                    Глубина <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    value={config.depth || ''}
                    onChange={e => onConfigChange({ ...config, depth: +e.target.value })}
                    className="w-full bg-transparent text-sm font-bold text-white outline-none font-mono"
                  />
                </div>
              </div>
            </div>

            {/* Base Type */}
            <div className="space-y-2">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                Основание
              </label>
              <VisualSelector
                value={config.baseType}
                onChange={v => onConfigChange({ ...config, baseType: v as 'plinth' | 'legs' })}
                options={[
                  { id: 'plinth', label: 'Цоколь', icon: PanelBottom },
                  { id: 'legs', label: 'Ножки', icon: Footprints },
                ]}
              />
            </div>

            {/* Door Type */}
            <div className="space-y-2">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                Фасады
              </label>
              <VisualSelector
                value={config.doorType}
                onChange={v => onConfigChange({ ...config, doorType: v as DoorType })}
                options={[
                  { id: 'none', label: 'Нет', icon: LayoutGrid },
                  { id: 'hinged', label: 'Распашные', icon: DoorOpen },
                  { id: 'sliding', label: 'Купе', icon: GripHorizontal },
                ]}
              />
              {config.doorType !== 'none' && (
                <div className="mt-2 space-y-2">
                  <div className="flex items-center gap-3 bg-[#1a1a1a] p-2 rounded border border-[#333]">
                    <span className="text-xs text-slate-400 flex-1">Количество дверей:</span>
                    <input
                      type="number"
                      min="1"
                      max="5"
                      value={config.doorCount}
                      onChange={e => onConfigChange({ ...config, doorCount: +e.target.value })}
                      className="w-12 bg-[#333] rounded px-2 py-1 text-sm text-center text-white outline-none focus:border-blue-500 border border-transparent"
                    />
                  </div>
                  {config.doorType === 'hinged' && (
                    <div className="flex items-center gap-3 bg-[#1a1a1a] p-2 rounded border border-[#333]">
                      <span className="text-xs text-slate-400 flex-1">Зазор (мм):</span>
                      <input
                        type="number"
                        min="0"
                        max="10"
                        value={config.doorGap}
                        onChange={e => onConfigChange({ ...config, doorGap: +e.target.value })}
                        className="w-12 bg-[#333] rounded px-2 py-1 text-sm text-center text-white outline-none focus:border-blue-500 border border-transparent"
                      />
                    </div>
                  )}
                  {config.doorType === 'sliding' && (
                    <div className="flex items-center gap-3 bg-[#1a1a1a] p-2 rounded border border-[#333]">
                      <span className="text-xs text-slate-400 flex-1">Перехлест (мм):</span>
                      <input
                        type="number"
                        min="0"
                        max="50"
                        value={config.coupeGap}
                        onChange={e => onConfigChange({ ...config, coupeGap: +e.target.value })}
                        className="w-12 bg-[#333] rounded px-2 py-1 text-sm text-center text-white outline-none focus:border-blue-500 border border-transparent"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
            {/* Distribute Button */}
            {sections[selectedSectionId] && sections[selectedSectionId].items.length > 1 && (
              <div className="bg-[#1a1a1a] p-3 rounded border border-blue-500/20">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-2">
                  Операции с секцией {selectedSectionId + 1}
                </label>
                <button
                  onClick={onDistributeItems}
                  className="w-full py-2 bg-slate-700 hover:bg-slate-600 text-white rounded text-xs flex items-center justify-center gap-2 transition border border-slate-600"
                  title="Распределить элементы равномерно по высоте"
                >
                  <StretchVertical size={14} /> Распределить равномерно
                </button>
              </div>
            )}

            {selectedItem ? (
              <div className="space-y-4">
                <div className="bg-[#1a1a1a] p-3 rounded border border-blue-500/30">
                  <div className="text-xs text-blue-400 font-bold uppercase mb-1">{selectedItem.name}</div>
                  <div className="text-[10px] text-slate-500">ID: {selectedItem.id.slice(-6)}</div>
                </div>

                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-2">
                    Положение (Y)
                  </label>
                  <div className="flex items-center bg-[#1a1a1a] border border-[#333] rounded p-1">
                    <input
                      type="number"
                      value={Math.round(selectedItem.y)}
                      onChange={e => onUpdateItem(selectedItem.id, { y: +e.target.value })}
                      className="w-full bg-transparent px-2 py-1 text-white font-mono"
                    />
                    <span className="text-xs text-slate-500 px-2">мм</span>
                  </div>
                </div>

                {selectedItem.type === 'drawer' && (
                  <div>
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-2">
                      Высота фасада
                    </label>
                    <div className="space-y-1">
                      {[140, 176, 200, 300].map(h => (
                        <button
                          key={h}
                          onClick={() => onUpdateItem(selectedItem.id, { height: h })}
                          className={`w-full text-left px-3 py-2 rounded text-xs flex justify-between ${
                            selectedItem.height === h
                              ? 'bg-blue-600 text-white'
                              : 'bg-[#333] text-slate-300 hover:bg-[#444]'
                          }`}
                        >
                          <span>{h} мм</span>
                          <span className="opacity-50">
                            {h === 140 ? 'Низкий' : h === 176 ? 'Стандарт' : h === 300 ? 'Глубокий' : ''}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {selectedItem.type === 'partition' && (
                  <div>
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-2">
                      Высота перегородки
                    </label>
                    <div className="flex items-center bg-[#1a1a1a] border border-[#333] rounded p-1">
                      <input
                        type="number"
                        value={Math.round(selectedItem.height || 300)}
                        onChange={e => onUpdateItem(selectedItem.id, { height: +e.target.value })}
                        className="w-full bg-transparent px-2 py-1 text-white font-mono"
                      />
                      <span className="text-xs text-slate-500 px-2">мм</span>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center text-slate-500 py-10">
                <MousePointer2 size={32} className="mx-auto mb-2 opacity-30" />
                <p className="text-xs">
                  Выберите элемент на схеме
                  <br />
                  для редактирования
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="p-5 border-t border-[#333] bg-[#222]">
        <button
          onClick={onGenerate}
          className="w-full py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-xl shadow-lg flex items-center justify-center gap-2 text-sm transition-all transform hover:scale-[1.02] group"
        >
          <MonitorPlay size={20} className="group-hover:animate-pulse" /> Построить Модель
        </button>
      </div>
    </div>
  );
};
