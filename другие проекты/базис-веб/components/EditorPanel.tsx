import React from 'react';
import { useProjectStore } from '../store/projectStore';
import { Material } from '../types';
import { useEditorPanelState } from '../hooks/useEditorPanelState';
import { useHardwareHelpers } from '../hooks/useHardwareHelpers';
import TopTabBar from './EditorPanel/TopTabBar';
import StructureView from './EditorPanel/StructureView';
import PropertiesView from './EditorPanel/PropertiesView';

interface EditorPanelProps {
  materialLibrary: Material[];
}

const EditorPanel: React.FC<EditorPanelProps> = ({ materialLibrary }) => {
  const {
    panels,
    selectedPanelId,
    updatePanel,
    deletePanel,
    duplicatePanel,
    selectPanel,
  } = useProjectStore();

  const { activeTab, setActiveTab, editTab, setEditTab, searchTerm, setSearchTerm } =
    useEditorPanelState(panels, selectedPanelId);

  const selectedPanel = panels.find((p) => p.id === selectedPanelId);
  const { addHardwarePreset, updateGroove } = useHardwareHelpers({
    selectedPanel,
    updatePanel,
  });

  return (
    <div className="w-full h-full bg-[#1e1e1e] flex flex-col shadow-2xl z-20 text-slate-300 no-scrollbar">
      <TopTabBar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        hasPanelSelected={!!selectedPanel}
      />

      <div className="flex-1 overflow-hidden relative bg-[#1e1e1e]">
        {activeTab === 'structure' && (
          <StructureView
            panels={panels}
            selectedPanelId={selectedPanelId}
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
            onSelectPanel={selectPanel}
            onToggleVisibility={(id, current) => updatePanel(id, { visible: !current })}
          />
        )}

        {activeTab === 'properties' && selectedPanel && (
          <PropertiesView
            panel={selectedPanel}
            materialLibrary={materialLibrary}
            activeEditTab={editTab}
            onEditTabChange={setEditTab}
            onUpdatePanel={updatePanel}
            onDuplicatePanel={duplicatePanel}
            onDeletePanel={deletePanel}
            onUpdateGroove={updateGroove}
            onAddHardwarePreset={addHardwarePreset}
          />
        )}
      </div>
    </div>
  );
};

export default EditorPanel;
