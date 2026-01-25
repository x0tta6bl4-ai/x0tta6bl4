import React, { useMemo } from 'react';
import { Panel } from '../../types';
import { Search, Eye, EyeOff, Layers, Box } from 'lucide-react';

interface StructureViewProps {
  panels: Panel[];
  selectedPanelId: string | null;
  searchTerm: string;
  onSearchChange: (term: string) => void;
  onSelectPanel: (id: string) => void;
  onToggleVisibility: (id: string, current: boolean) => void;
}

const StructureView: React.FC<StructureViewProps> = ({
  panels,
  selectedPanelId,
  searchTerm,
  onSearchChange,
  onSelectPanel,
  onToggleVisibility,
}) => {
  const filteredPanels = useMemo(
    () =>
      panels.filter((p) => p.name.toLowerCase().includes(searchTerm.toLowerCase())),
    [panels, searchTerm]
  );

  const groupedPanels = useMemo(() => {
    const groups: Record<string, Panel[]> = {};
    filteredPanels.forEach((p) => {
      const groupName =
        p.layer === 'body'
          ? 'Корпус'
          : p.layer === 'facade'
          ? 'Фасады'
          : p.layer === 'shelves'
          ? 'Полки'
          : p.layer === 'back'
          ? 'Задняя стенка'
          : 'Фурнитура';
      if (!groups[groupName]) groups[groupName] = [];
      groups[groupName].push(p);
    });
    return groups;
  }, [filteredPanels]);

  return (
    <div className="h-full flex flex-col">
      <div className="p-3 border-b border-slate-700 bg-[#252526]">
        <div className="relative">
          <Search className="absolute left-2 top-2 text-slate-500" size={14} />
          <input
            type="text"
            placeholder="Поиск детали..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-[#1a1a1a] border border-slate-600 rounded pl-8 pr-2 py-1.5 text-xs text-white focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div className="flex justify-between mt-2 text-[10px] text-slate-500 px-1">
          <span>Всего деталей: {panels.length}</span>
          <span>Выбрано: {selectedPanelId ? 1 : 0}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 no-scrollbar space-y-4">
        {Object.keys(groupedPanels).length === 0 && (
          <div className="text-center text-slate-500 py-10 text-xs">
            Нет деталей в проекте
          </div>
        )}

        {(Object.entries(groupedPanels) as [string, Panel[]][]).map(
          ([groupName, groupItems]) => (
            <div key={groupName}>
              <div className="text-[10px] font-bold text-blue-500 uppercase px-2 mb-1 flex items-center gap-2">
                <Layers size={12} /> {groupName}
              </div>
              <div className="space-y-0.5">
                {groupItems.map((p) => (
                  <div
                    key={p.id}
                    onClick={() => onSelectPanel(p.id)}
                    className={`flex items-center gap-2 p-2 rounded cursor-pointer border border-transparent transition group ${
                      p.id === selectedPanelId
                        ? 'bg-blue-600 text-white'
                        : 'hover:bg-slate-800 hover:border-slate-700 text-slate-400'
                    }`}
                  >
                    <Box
                      size={14}
                      className={
                        p.id === selectedPanelId
                          ? 'text-white'
                          : 'text-slate-600'
                      }
                    />
                    <div className="flex-1 min-w-0">
                      <div
                        className={`text-xs font-medium truncate ${
                          p.id === selectedPanelId
                            ? 'text-white'
                            : 'text-slate-300'
                        }`}
                      >
                        {p.name}
                      </div>
                      <div
                        className={`text-[10px] font-mono ${
                          p.id === selectedPanelId
                            ? 'text-blue-200'
                            : 'text-slate-600'
                        }`}
                      >
                        {p.width} x {p.height}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleVisibility(p.id, p.visible);
                      }}
                      className={`p-1 rounded hover:bg-black/20 ${
                        p.visible ? '' : 'text-slate-600'
                      }`}
                    >
                      {p.visible ? (
                        <Eye size={14} />
                      ) : (
                        <EyeOff size={14} />
                      )}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
};

export default StructureView;
