import React from 'react';
import { FileText, Save, FolderOpen, Settings, HelpCircle, Menu, X } from 'lucide-react';

interface NavigationBarProps {
  projectName: string;
  onMenuToggle: () => void;
  menuOpen: boolean;
  onSave: () => void;
  onLoad: () => void;
  onSettings: () => void;
  isDirty: boolean;
}

export const NavigationBar: React.FC<NavigationBarProps> = ({
  projectName,
  onMenuToggle,
  menuOpen,
  onSave,
  onLoad,
  onSettings,
  isDirty
}) => {
  return (
    <nav className="bg-gradient-to-r from-slate-900 to-slate-800 text-white shadow-lg border-b border-slate-700">
      <div className="px-4 py-3 flex items-center justify-between">
        {/* Logo & Project Name */}
        <div className="flex items-center gap-3">
          <button
            onClick={onMenuToggle}
            className="p-2 hover:bg-slate-700 rounded transition-colors lg:hidden"
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          
          <div className="flex items-center gap-2">
            <FileText size={24} className="text-blue-400" />
            <div>
              <h1 className="font-bold text-lg">BazisLite CAD</h1>
              <p className="text-xs text-slate-400">{projectName}</p>
            </div>
          </div>
        </div>

        {/* Middle Section - File Menu */}
        <div className="hidden md:flex items-center gap-2">
          <button
            onClick={onSave}
            className={`px-3 py-2 rounded hover:bg-slate-700 transition-colors flex items-center gap-1 ${
              isDirty ? 'text-yellow-400' : 'text-slate-300'
            }`}
            title="Сохранить проект"
          >
            <Save size={18} />
            <span className="text-sm">Сохранить</span>
          </button>
          
          <button
            onClick={onLoad}
            className="px-3 py-2 rounded hover:bg-slate-700 transition-colors flex items-center gap-1 text-slate-300"
            title="Открыть проект"
          >
            <FolderOpen size={18} />
            <span className="text-sm">Открыть</span>
          </button>
        </div>

        {/* Right Section - Settings & Help */}
        <div className="flex items-center gap-2">
          <button
            onClick={onSettings}
            className="p-2 hover:bg-slate-700 rounded transition-colors"
            title="Настройки"
          >
            <Settings size={20} />
          </button>
          
          <a
            href="#help"
            className="p-2 hover:bg-slate-700 rounded transition-colors"
            title="Помощь"
          >
            <HelpCircle size={20} />
          </a>
        </div>
      </div>
    </nav>
  );
};
