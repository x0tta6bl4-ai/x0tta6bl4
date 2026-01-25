import React from 'react';
import { Trash2, Columns } from 'lucide-react';
import { CabinetItem } from '../../types';
import { ToolButton, MinusIcon, ArchiveBoxIcon, CircleIcon } from './shared';
import { RectangleVertical } from 'lucide-react';

interface ToolsPanelProps {
  onAddItem: (type: CabinetItem['type']) => void;
  onAddSection: () => void;
  onDelete: () => void;
  hasSelection: boolean;
}

export const ToolsPanel: React.FC<ToolsPanelProps> = ({
  onAddItem,
  onAddSection,
  onDelete,
  hasSelection,
}) => {
  return (
    <div className="w-20 bg-[#252526] border-r border-[#333] flex flex-col items-center py-6 gap-3 z-20 shrink-0 shadow-xl">
      <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest text-center w-full mb-1">
        Добавить
      </div>
      <ToolButton onClick={() => onAddItem('shelf')} label="Полка" icon={MinusIcon} />
      <ToolButton onClick={() => onAddItem('drawer')} label="Ящик" icon={ArchiveBoxIcon} />
      <ToolButton onClick={() => onAddItem('rod')} label="Штанга" icon={CircleIcon} />
      <ToolButton onClick={() => onAddItem('partition')} label="Перегородка" icon={RectangleVertical} />
      <div className="w-8 h-px bg-[#444] my-2"></div>
      <ToolButton onClick={onAddSection} label="+Секция" icon={Columns} colorClass="hover:bg-emerald-600" />
      <ToolButton
        onClick={onDelete}
        label="Удалить"
        icon={Trash2}
        colorClass="hover:bg-red-600"
        title={hasSelection ? 'Удалить элемент' : 'Удалить секцию'}
      />
    </div>
  );
};
