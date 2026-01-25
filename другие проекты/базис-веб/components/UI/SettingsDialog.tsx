import React, { useState } from 'react';
import { X, Moon, Sun, Monitor } from 'lucide-react';

type Theme = 'dark' | 'light' | 'auto';

interface SettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  settings: {
    theme: Theme;
    showGrid: boolean;
    snapToGrid: boolean;
    autoSave: boolean;
    autoSaveInterval: number;
  };
  onSettingsChange: (settings: any) => void;
}

export const SettingsDialog: React.FC<SettingsDialogProps> = ({
  isOpen,
  onClose,
  settings,
  onSettingsChange
}) => {
  const [localSettings, setLocalSettings] = useState(settings);

  if (!isOpen) return null;

  const handleSave = () => {
    onSettingsChange(localSettings);
    onClose();
  };

  const handleChange = (key: string, value: any) => {
    setLocalSettings({ ...localSettings, [key]: value });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-slate-900 rounded-lg shadow-2xl max-w-md w-full mx-4 border border-slate-700">
        {/* Header */}
        <div className="flex items-center justify-between bg-slate-800 px-6 py-4 border-b border-slate-700">
          <h2 className="text-white font-bold">Настройки</h2>
          <button onClick={onClose} className="p-1 hover:bg-slate-700 rounded transition-colors">
            <X size={20} className="text-slate-300" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 max-h-96 overflow-y-auto">
          {/* Theme Setting */}
          <div>
            <h3 className="text-white font-semibold text-sm mb-3">Тема</h3>
            <div className="grid grid-cols-3 gap-2">
              {(['dark', 'light', 'auto'] as const).map((theme) => (
                <button
                  key={theme}
                  onClick={() => handleChange('theme', theme)}
                  className={`p-3 rounded border-2 transition-all flex flex-col items-center gap-1 ${
                    localSettings.theme === theme
                      ? 'border-blue-500 bg-blue-900/20'
                      : 'border-slate-600 hover:border-slate-500'
                  }`}
                >
                  {theme === 'dark' && <Moon size={20} className="text-slate-300" />}
                  {theme === 'light' && <Sun size={20} className="text-yellow-400" />}
                  {theme === 'auto' && <Monitor size={20} className="text-slate-400" />}
                  <span className="text-xs text-slate-400 capitalize">
                    {theme === 'dark' ? 'Темная' : theme === 'light' ? 'Светлая' : 'Авто'}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Grid Settings */}
          <div className="space-y-3 border-t border-slate-700 pt-6">
            <h3 className="text-white font-semibold text-sm">Сетка</h3>

            <label className="flex items-center gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={localSettings.showGrid}
                onChange={(e) => handleChange('showGrid', e.target.checked)}
                className="w-4 h-4 rounded border border-slate-600 cursor-pointer accent-blue-500"
              />
              <span className="text-slate-300 group-hover:text-white transition-colors">
                Показывать сетку по умолчанию
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={localSettings.snapToGrid}
                onChange={(e) => handleChange('snapToGrid', e.target.checked)}
                className="w-4 h-4 rounded border border-slate-600 cursor-pointer accent-blue-500"
              />
              <span className="text-slate-300 group-hover:text-white transition-colors">
                Привязка к сетке
              </span>
            </label>
          </div>

          {/* Auto Save */}
          <div className="space-y-3 border-t border-slate-700 pt-6">
            <h3 className="text-white font-semibold text-sm">Автосохранение</h3>

            <label className="flex items-center gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={localSettings.autoSave}
                onChange={(e) => handleChange('autoSave', e.target.checked)}
                className="w-4 h-4 rounded border border-slate-600 cursor-pointer accent-blue-500"
              />
              <span className="text-slate-300 group-hover:text-white transition-colors">
                Включить автосохранение
              </span>
            </label>

            {localSettings.autoSave && (
              <div>
                <label className="text-xs text-slate-400 block mb-2">Интервал (сек)</label>
                <input
                  type="number"
                  value={localSettings.autoSaveInterval}
                  onChange={(e) =>
                    handleChange('autoSaveInterval', Math.max(5, Number(e.target.value)))
                  }
                  min={5}
                  step={5}
                  className="w-full bg-slate-800 text-white rounded px-3 py-2 border border-slate-700 focus:border-blue-500 focus:outline-none"
                />
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-2 px-6 py-4 bg-slate-800 border-t border-slate-700">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded font-semibold transition-colors"
          >
            Отмена
          </button>
          <button
            onClick={handleSave}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold transition-colors"
          >
            Сохранить
          </button>
        </div>
      </div>
    </div>
  );
};
