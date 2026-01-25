import React from 'react';
import { Undo2, Redo2, Trash2, Copy, Clipboard, Save, Eye, EyeOff, Lock, Unlock, Grid, Box } from 'lucide-react';

interface ToolbarProps {
  onUndo: () => void;
  onRedo: () => void;
  onDelete: () => void;
  onCopy: () => void;
  onPaste: () => void;
  onSave: () => void;
  canUndo: boolean;
  canRedo: boolean;
  hasSelection: boolean;
  canPaste: boolean;
  onToggleGrid?: () => void;
  onToggle3D?: () => void;
  view3DEnabled?: boolean;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  onUndo,
  onRedo,
  onDelete,
  onCopy,
  onPaste,
  onSave,
  canUndo,
  canRedo,
  hasSelection,
  canPaste,
  onToggleGrid,
  onToggle3D,
  view3DEnabled = false
}) => {
  const toolButtonClass = (enabled: boolean) => `
    px-3 py-2 rounded transition-colors flex items-center gap-1 text-sm font-medium
    ${enabled 
      ? 'bg-slate-700 text-slate-100 hover:bg-slate-600 cursor-pointer' 
      : 'bg-slate-800 text-slate-500 cursor-not-allowed opacity-50'
    }
  `;

  return (
    <div className="bg-slate-800 border-b border-slate-700 px-4 py-2 flex items-center gap-1 flex-wrap overflow-x-auto">
      {/* Edit Tools */}
      <div className="flex items-center gap-1 border-r border-slate-600 pr-2">
        <button
          onClick={onUndo}
          disabled={!canUndo}
          className={toolButtonClass(canUndo)}
          title="Отменить (Ctrl+Z)"
        >
          <Undo2 size={16} />
          <span className="hidden sm:inline">Отменить</span>
        </button>

        <button
          onClick={onRedo}
          disabled={!canRedo}
          className={toolButtonClass(canRedo)}
          title="Повторить (Ctrl+Y)"
        >
          <Redo2 size={16} />
          <span className="hidden sm:inline">Повторить</span>
        </button>
      </div>

      {/* Clipboard Tools */}
      <div className="flex items-center gap-1 border-r border-slate-600 pr-2">
        <button
          onClick={onCopy}
          disabled={!hasSelection}
          className={toolButtonClass(hasSelection)}
          title="Копировать (Ctrl+C)"
        >
          <Copy size={16} />
          <span className="hidden sm:inline">Копировать</span>
        </button>

        <button
          onClick={onPaste}
          disabled={!canPaste}
          className={toolButtonClass(canPaste)}
          title="Вставить (Ctrl+V)"
        >
          <Clipboard size={16} />
          <span className="hidden sm:inline">Вставить</span>
        </button>

        <button
          onClick={onDelete}
          disabled={!hasSelection}
          className={toolButtonClass(hasSelection)}
          title="Удалить (Delete)"
        >
          <Trash2 size={16} />
          <span className="hidden sm:inline">Удалить</span>
        </button>
      </div>

      {/* File Tools */}
      <div className="flex items-center gap-1 border-r border-slate-600 pr-2">
        <button
          onClick={onSave}
          className={toolButtonClass(true)}
          title="Сохранить (Ctrl+S)"
        >
          <Save size={16} />
          <span className="hidden sm:inline">Сохранить</span>
        </button>
      </div>

      {/* View Tools */}
      <div className="flex items-center gap-1">
        {onToggleGrid && (
          <button
            onClick={onToggleGrid}
            className={toolButtonClass(true)}
            title="Сетка"
          >
            <Grid size={16} />
            <span className="hidden sm:inline">Сетка</span>
          </button>
        )}

        {onToggle3D && (
          <button
            onClick={onToggle3D}
            className={`px-3 py-2 rounded transition-colors flex items-center gap-1 text-sm font-medium ${
              view3DEnabled
                ? 'bg-blue-600 text-white hover:bg-blue-500'
                : 'bg-slate-700 text-slate-100 hover:bg-slate-600'
            }`}
            title="3D вид (F3)"
          >
            <Box size={16} />
            <span className="hidden sm:inline">3D</span>
          </button>
        )}
      </div>
    </div>
  );
};
