import React, { useState } from 'react';
import { ChevronRight, ChevronDown, Eye, EyeOff, Lock, Unlock, Trash2 } from 'lucide-react';
import { Layer, Panel } from '../../types';

interface SidePanelProps {
  layers: Layer[];
  panels: Panel[];
  selectedPanelId: string | null;
  onSelectPanel: (id: string) => void;
  onToggleLayerVisibility: (id: string) => void;
  onToggleLayerLocked: (id: string) => void;
  onDeletePanel: (id: string) => void;
  onRenamePanel: (id: string, name: string) => void;
}

export const SidePanel: React.FC<SidePanelProps> = ({
  layers,
  panels,
  selectedPanelId,
  onSelectPanel,
  onToggleLayerVisibility,
  onToggleLayerLocked,
  onDeletePanel,
  onRenamePanel
}) => {
  const [expandedLayers, setExpandedLayers] = useState<Set<string>>(new Set(['body', 'facade', 'back', 'shelves']));
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renamingText, setRenamingText] = useState('');

  const toggleLayerExpand = (id: string) => {
    const newExpanded = new Set(expandedLayers);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedLayers(newExpanded);
  };

  const startRename = (panel: Panel) => {
    setRenamingId(panel.id);
    setRenamingText(panel.name);
  };

  const finishRename = () => {
    if (renamingId && renamingText.trim()) {
      onRenamePanel(renamingId, renamingText);
    }
    setRenamingId(null);
  };

  return (
    <div className="bg-slate-900 border-r border-slate-700 w-64 h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="bg-slate-800 px-4 py-3 border-b border-slate-700">
        <h2 className="text-white font-semibold text-sm">Слои и объекты</h2>
      </div>

      {/* Layers Tree */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-2">
          {layers.map((layer) => {
            const layerPanels = panels.filter(p => p.layer === layer.id);
            const isExpanded = expandedLayers.has(layer.id);

            return (
              <div key={layer.id} className="mb-2">
                {/* Layer Header */}
                <div className="flex items-center gap-2 px-2 py-1 hover:bg-slate-800 rounded transition-colors group">
                  <button
                    onClick={() => toggleLayerExpand(layer.id)}
                    className="p-0.5 hover:bg-slate-700 rounded transition-colors"
                  >
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </button>

                  <span
                    style={{ backgroundColor: layer.color }}
                    className="w-3 h-3 rounded opacity-60"
                  />

                  <span className="flex-1 text-slate-300 text-sm font-medium">
                    {layer.name}
                  </span>

                  <button
                    onClick={() => onToggleLayerVisibility(layer.id)}
                    className="p-0.5 opacity-0 group-hover:opacity-100 hover:bg-slate-700 rounded transition-all"
                    title={layer.visible ? 'Скрыть' : 'Показать'}
                  >
                    {layer.visible ? (
                      <Eye size={14} className="text-slate-400" />
                    ) : (
                      <EyeOff size={14} className="text-slate-500" />
                    )}
                  </button>

                  <button
                    onClick={() => onToggleLayerLocked(layer.id)}
                    className="p-0.5 opacity-0 group-hover:opacity-100 hover:bg-slate-700 rounded transition-all"
                    title={layer.locked ? 'Разблокировать' : 'Блокировать'}
                  >
                    {layer.locked ? (
                      <Lock size={14} className="text-slate-400" />
                    ) : (
                      <Unlock size={14} className="text-slate-500" />
                    )}
                  </button>
                </div>

                {/* Panels in Layer */}
                {isExpanded && (
                  <div className="ml-4 mt-1 space-y-1">
                    {layerPanels.length > 0 ? (
                      layerPanels.map((panel) => (
                        <div
                          key={panel.id}
                          onClick={() => onSelectPanel(panel.id)}
                          className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors group ${
                            selectedPanelId === panel.id
                              ? 'bg-blue-600 text-white'
                              : 'hover:bg-slate-800 text-slate-300'
                          }`}
                        >
                          <div className="w-3 h-3 rounded border border-slate-500" />

                          {renamingId === panel.id ? (
                            <input
                              autoFocus
                              value={renamingText}
                              onChange={(e) => setRenamingText(e.target.value)}
                              onBlur={finishRename}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') finishRename();
                                if (e.key === 'Escape') setRenamingId(null);
                              }}
                              className="flex-1 bg-slate-700 rounded px-1 py-0 text-xs text-white"
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <span
                              onDoubleClick={() => startRename(panel)}
                              className="flex-1 text-xs truncate"
                            >
                              {panel.name}
                            </span>
                          )}

                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeletePanel(panel.id);
                            }}
                            className="p-0.5 opacity-0 group-hover:opacity-100 hover:bg-red-600/20 rounded transition-all"
                            title="Удалить"
                          >
                            <Trash2 size={12} className="text-red-400" />
                          </button>
                        </div>
                      ))
                    ) : (
                      <div className="px-2 py-1 text-xs text-slate-500 italic">
                        Нет объектов
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="bg-slate-800 border-t border-slate-700 px-4 py-2 text-xs text-slate-400">
        Всего: {panels.length} объектов
      </div>
    </div>
  );
};
