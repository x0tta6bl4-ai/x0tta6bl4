import React, { useState } from 'react';
import { X, Download, Upload, Trash2 } from 'lucide-react';

interface FileDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSave?: (filename: string) => void;
  onLoad?: (filename: string) => void;
  recentFiles?: string[];
  onDeleteFile?: (filename: string) => void;
}

export const FileDialog: React.FC<FileDialogProps> = ({
  isOpen,
  onClose,
  onSave,
  onLoad,
  recentFiles = [],
  onDeleteFile
}) => {
  const [filename, setFilename] = useState('');
  const [activeTab, setActiveTab] = useState<'save' | 'load'>('load');

  if (!isOpen) return null;

  const handleSave = () => {
    if (filename.trim() && onSave) {
      onSave(filename);
      setFilename('');
      onClose();
    }
  };

  const handleLoad = (file: string) => {
    if (onLoad) {
      onLoad(file);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-slate-900 rounded-lg shadow-2xl max-w-md w-full mx-4 border border-slate-700">
        {/* Header */}
        <div className="flex items-center justify-between bg-slate-800 px-6 py-4 border-b border-slate-700">
          <h2 className="text-white font-bold">Файлы проекта</h2>
          <button onClick={onClose} className="p-1 hover:bg-slate-700 rounded transition-colors">
            <X size={20} className="text-slate-300" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 px-6 pt-4 border-b border-slate-700">
          <button
            onClick={() => setActiveTab('load')}
            className={`pb-3 px-4 font-semibold text-sm border-b-2 transition-colors ${
              activeTab === 'load'
                ? 'border-blue-500 text-white'
                : 'border-transparent text-slate-400 hover:text-slate-300'
            }`}
          >
            <Upload size={14} className="inline mr-2" />
            Загрузить
          </button>
          <button
            onClick={() => setActiveTab('save')}
            className={`pb-3 px-4 font-semibold text-sm border-b-2 transition-colors ${
              activeTab === 'save'
                ? 'border-blue-500 text-white'
                : 'border-transparent text-slate-400 hover:text-slate-300'
            }`}
          >
            <Download size={14} className="inline mr-2" />
            Сохранить
          </button>
        </div>

        {/* Content */}
        <div className="p-6 max-h-96 overflow-y-auto">
          {activeTab === 'load' && (
            <div className="space-y-2">
              {recentFiles.length > 0 ? (
                recentFiles.map((file) => (
                  <div
                    key={file}
                    className="flex items-center justify-between p-3 bg-slate-800 hover:bg-slate-700 rounded cursor-pointer transition-colors group"
                  >
                    <button
                      onClick={() => handleLoad(file)}
                      className="flex-1 text-left text-slate-300 hover:text-white font-medium"
                    >
                      {file}
                    </button>
                    <button
                      onClick={() => onDeleteFile?.(file)}
                      className="p-1 opacity-0 group-hover:opacity-100 hover:bg-red-600/20 rounded transition-all"
                    >
                      <Trash2 size={16} className="text-red-400" />
                    </button>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-slate-500">Нет сохраненных файлов</div>
              )}
            </div>
          )}

          {activeTab === 'save' && (
            <div className="space-y-4">
              <div>
                <label className="text-sm text-slate-400 block mb-2">Имя файла</label>
                <input
                  type="text"
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  placeholder="Введите имя проекта..."
                  className="w-full bg-slate-800 text-white rounded px-3 py-2 border border-slate-700 focus:border-blue-500 focus:outline-none"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSave();
                  }}
                />
              </div>

              <p className="text-xs text-slate-500">
                Расширение .bazis будет добавлено автоматически
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-2 px-6 py-4 bg-slate-800 border-t border-slate-700">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded font-semibold transition-colors"
          >
            Отмена
          </button>
          {activeTab === 'save' && (
            <button
              onClick={handleSave}
              disabled={!filename.trim()}
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-900 disabled:opacity-50 text-white rounded font-semibold transition-colors"
            >
              Сохранить
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
