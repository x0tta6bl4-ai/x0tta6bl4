import React, { useCallback } from 'react';
import { Panel } from '../../types';
import { Trash2, Copy } from 'lucide-react';
import PanelDrawing from '../PanelDrawing';
import NameInput from '../NameInput';
import { inputValidator } from '../../services/InputValidator';

interface PropertiesHeaderProps {
  panel: Panel;
  onUpdatePanel: (id: string, updates: Partial<Panel>) => void;
  onDuplicatePanel: (id: string) => void;
  onDeletePanel: (id: string) => void;
}

const PropertiesHeader: React.FC<PropertiesHeaderProps> = ({
  panel,
  onUpdatePanel,
  onDuplicatePanel,
  onDeletePanel,
}) => {
  const handleNameChange = useCallback(
    (name: string) => {
      const result = inputValidator.validateInput(
        name,
        { type: 'string', required: true },
        'Имя'
      );
      if (result.isValid && result.sanitized) {
        onUpdatePanel(panel.id, { name: String(result.sanitized) });
      }
    },
    [panel.id, onUpdatePanel]
  );

  return (
    <div className="p-4 bg-[#252526] border-b border-slate-700 shrink-0">
      <div className="flex justify-between items-center mb-4">
        <NameInput
          label="Имя"
          value={panel.name}
          onChange={handleNameChange}
          maxLength={100}
        />
        <div className="flex gap-1">
          <button
            onClick={() => onDuplicatePanel(panel.id)}
            className="p-2 hover:bg-slate-700 rounded text-slate-400"
            title="Дублировать"
          >
            <Copy size={14} />
          </button>
          <button
            onClick={() => onDeletePanel(panel.id)}
            className="p-2 hover:bg-red-900/30 rounded text-red-500"
            title="Удалить"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      <div className="h-24 bg-slate-900 rounded-lg border border-slate-800 overflow-hidden flex items-center justify-center relative">
        <div className="absolute inset-0 opacity-50 pointer-events-none">
          <PanelDrawing
            panel={panel}
            width={300}
            height={128}
            detailed={false}
          />
        </div>
      </div>
    </div>
  );
};

export default PropertiesHeader;
