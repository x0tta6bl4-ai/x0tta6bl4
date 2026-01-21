import React from 'react';
import { Panel, Material } from '../../types';
import PropertiesHeader from './PropertiesHeader';
import PropertiesTabBar from './PropertiesTabBar';
import MainPropertiesTab from './MainPropertiesTab';
import EdgeTab from './EdgeTab';
import DrillingTab from './DrillingTab';
import HardwareTab from './HardwareTab';

interface PropertiesViewProps {
  panel: Panel;
  materialLibrary: Material[];
  activeEditTab: 'main' | 'edge' | 'drilling' | 'hardware';
  onEditTabChange: (tab: 'main' | 'edge' | 'drilling' | 'hardware') => void;
  onUpdatePanel: (id: string, updates: Partial<Panel>) => void;
  onDuplicatePanel: (id: string) => void;
  onDeletePanel: (id: string) => void;
  onUpdateGroove: (changes: Record<string, any>) => void;
  onAddHardwarePreset: (preset: 'hinge' | 'rail' | 'handle' | 'mounting') => void;
}

const PropertiesView: React.FC<PropertiesViewProps> = ({
  panel,
  materialLibrary,
  activeEditTab,
  onEditTabChange,
  onUpdatePanel,
  onDuplicatePanel,
  onDeletePanel,
  onUpdateGroove,
  onAddHardwarePreset,
}) => (
  <div className="h-full flex flex-col">
    <PropertiesHeader
      panel={panel}
      onUpdatePanel={onUpdatePanel}
      onDuplicatePanel={onDuplicatePanel}
      onDeletePanel={onDeletePanel}
    />

    <PropertiesTabBar
      activeTab={activeEditTab}
      onTabChange={onEditTabChange}
    />

    <div className="flex-1 overflow-y-auto p-4 space-y-6 no-scrollbar">
      {activeEditTab === 'main' && (
        <MainPropertiesTab
          panel={panel}
          materialLibrary={materialLibrary}
          onUpdatePanel={onUpdatePanel}
        />
      )}

      {activeEditTab === 'edge' && (
        <EdgeTab panel={panel} onUpdatePanel={onUpdatePanel} />
      )}

      {activeEditTab === 'drilling' && (
        <DrillingTab
          panel={panel}
          onUpdatePanel={onUpdatePanel}
          onUpdateGroove={onUpdateGroove}
        />
      )}

      {activeEditTab === 'hardware' && (
        <HardwareTab onAddHardwarePreset={onAddHardwarePreset} />
      )}
    </div>
  </div>
);

export default PropertiesView;
