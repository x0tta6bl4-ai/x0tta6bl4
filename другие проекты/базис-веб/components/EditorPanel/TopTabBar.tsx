import React from 'react';
import { ListTree, SlidersHorizontal } from 'lucide-react';

interface TopTabBarProps {
  activeTab: 'structure' | 'properties';
  onTabChange: (tab: 'structure' | 'properties') => void;
  hasPanelSelected: boolean;
}

const TopTabBar: React.FC<TopTabBarProps> = ({
  activeTab,
  onTabChange,
  hasPanelSelected,
}) => (
  <div className="flex border-b border-slate-700 bg-[#252526] shrink-0">
    <button
      onClick={() => onTabChange('structure')}
      className={`flex-1 py-3 text-[10px] md:text-xs font-bold uppercase flex items-center justify-center gap-2 transition ${
        activeTab === 'structure'
          ? 'text-blue-400 bg-slate-800 border-b-2 border-blue-500'
          : 'text-slate-500 hover:text-white'
      }`}
    >
      <ListTree size={16} /> Структура
    </button>
    <button
      onClick={() => {
        if (hasPanelSelected) onTabChange('properties');
      }}
      disabled={!hasPanelSelected}
      className={`flex-1 py-3 text-[10px] md:text-xs font-bold uppercase flex items-center justify-center gap-2 transition ${
        activeTab === 'properties'
          ? 'text-blue-400 bg-slate-800 border-b-2 border-blue-500'
          : 'text-slate-500 hover:text-white disabled:opacity-30'
      }`}
    >
      <SlidersHorizontal size={16} /> Свойства
    </button>
  </div>
);

export default TopTabBar;
