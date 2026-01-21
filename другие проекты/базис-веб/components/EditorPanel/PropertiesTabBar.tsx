import React from 'react';
import { TabButton } from './shared';

interface PropertiesTabBarProps {
  activeTab: 'main' | 'edge' | 'drilling' | 'hardware';
  onTabChange: (tab: 'main' | 'edge' | 'drilling' | 'hardware') => void;
}

const PropertiesTabBar: React.FC<PropertiesTabBarProps> = ({
  activeTab,
  onTabChange,
}) => (
  <div className="flex border-b border-slate-700 bg-[#252526] shrink-0 overflow-x-auto no-scrollbar">
    <TabButton
      active={activeTab === 'main'}
      onClick={() => onTabChange('main')}
      label="Основные"
    />
    <TabButton
      active={activeTab === 'edge'}
      onClick={() => onTabChange('edge')}
      label="Кромка"
    />
    <TabButton
      active={activeTab === 'drilling'}
      onClick={() => onTabChange('drilling')}
      label="Присадка"
    />
    <TabButton
      active={activeTab === 'hardware'}
      onClick={() => onTabChange('hardware')}
      label="Фурнитура"
    />
  </div>
);

export default PropertiesTabBar;
