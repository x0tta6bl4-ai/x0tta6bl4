
import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Save, FileCode, HelpCircle, FileJson, X } from 'lucide-react';

interface ScriptEditorProps {
  code: string;
  onChange: (code: string) => void;
  onRun: (code: string) => void;
}

const DEFAULT_SCRIPT = `// ============================================================================
// ADVANCED CABINET DESIGN SCRIPT
// Демонстрация всех возможностей Базис-Веб
// ============================================================================

// Габариты изделия
const W = 1800; 
const H = 2500; 
const D = 650;

// Настройки
const BASE_H = 70; // Цоколь
const MAT_TH = 16; 

DeleteAll();

// 1. КОРПУС
const sideL = AddPanel(D, H, MAT_TH).setName('Бок Левый').setOrient('X').setMaterial('eg-w980');
sideL.setPos(0, 0, 0).addEdging('bottom', 'right');
// Добавляем паз для задней стенки (ширина 4, глубина 10, отступ 20)
sideL.addGroove(4, 10, 20, 'top'); 

const sideR = AddPanel(D, H, MAT_TH).setName('Бок Правый').setOrient('X').setMaterial('eg-w980');
sideR.setPos(W - MAT_TH, 0, 0).addEdging('bottom', 'right');
sideR.addGroove(4, 10, 20, 'top');

const top = AddPanel(W, D, MAT_TH).setName('Крышка').setOrient('Y').setMaterial('eg-w980');
top.setPos(0, H - MAT_TH, 0).addEdging('top', 'left', 'right');
top.addGroove(4, 10, 20, 'bottom');

const bottom = AddPanel(W - 2*MAT_TH, D, MAT_TH).setName('Дно').setOrient('Y').setMaterial('eg-w980');
bottom.setPos(MAT_TH, BASE_H, 0).addEdging('top');

// 2. ФУРНИТУРА (Присадка)
// Полкодержатели на боковинах
const shelfY = H - 400;
sideL.addHardware('shelf_support', 100, shelfY);
sideL.addHardware('shelf_support', D-100, shelfY);
sideR.addHardware('shelf_support', 100, shelfY);
sideR.addHardware('shelf_support', D-100, shelfY);

// Шток эксцентрика на крышке
top.addHardware('minifix_pin', 50, 9);
top.addHardware('minifix_pin', D-50, 9);

// 3. НАПОЛНЕНИЕ
// Полка антресольная
const shelf = AddPanel(W - 2*MAT_TH, D - 20, MAT_TH).setName('Полка').setOrient('Y').setMaterial('eg-w980');
shelf.setPos(MAT_TH, shelfY, 0).addEdging('top');

// 4. ЗАДНЯЯ СТЕНКА
const back = AddPanel(W - 4, H - 4, 4).setName('Задняя стенка').setOrient('Z').setMaterial('HDF');
back.setPos(2, 2, 0);

alert('Проект создан успешно!');
`;

const ScriptEditor: React.FC<ScriptEditorProps> = ({ code, onChange, onRun }) => {
  const [showDocs, setShowDocs] = useState(false); // Default hidden on mobile, maybe desktop too for cleanliness

  useEffect(() => {
    if (!code) {
      onChange(DEFAULT_SCRIPT);
    }
    // Auto show docs on large screens initially
    if (window.innerWidth > 768) setShowDocs(true);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const target = e.target as HTMLTextAreaElement;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const value = target.value;
      target.value = value.substring(0, start) + '  ' + value.substring(end);
      target.selectionStart = target.selectionEnd = start + 2;
      onChange(target.value);
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        onRun(code);
    }
  };

  return (
    <div className="flex h-full bg-[#1e1e1e] text-gray-300 font-mono text-sm overflow-hidden relative">
      {/* Editor Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="bg-[#252526] p-2 flex items-center justify-between border-b border-[#333] shrink-0">
          <div className="flex items-center gap-2 text-blue-400 font-bold overflow-hidden">
            <FileCode size={18} className="shrink-0" />
            <span className="truncate">script.js</span>
          </div>
          <div className="flex gap-2">
            <button 
                onClick={() => onChange(DEFAULT_SCRIPT)}
                className="hidden sm:flex items-center gap-2 px-3 py-1 bg-[#333] hover:bg-[#444] rounded text-xs transition"
                title="Сбросить к примеру"
            >
                <RotateCcw size={14} /> Сброс
            </button>
            <button 
                onClick={() => setShowDocs(!showDocs)}
                className={`flex items-center gap-2 px-3 py-1 rounded text-xs transition ${showDocs ? 'bg-[#3e3e42] text-white' : 'bg-[#333] hover:bg-[#444]'}`}
            >
                <HelpCircle size={14} /> <span className="hidden sm:inline">Справка</span>
            </button>
            <button 
                onClick={() => onRun(code)}
                className="flex items-center gap-2 px-4 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-xs font-bold transition shadow-lg shadow-green-900/20"
                title="Запустить (Ctrl+Enter)"
            >
                <Play size={14} fill="currentColor" /> <span className="hidden sm:inline">Запустить</span>
            </button>
          </div>
        </div>
        <textarea
          value={code}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          className="flex-1 w-full bg-[#1e1e1e] text-[#d4d4d4] p-4 resize-none focus:outline-none leading-relaxed no-scrollbar"
          spellCheck={false}
          style={{ fontFamily: '"Fira Code", "Consolas", monospace' }}
        />
      </div>

      {/* Documentation Sidebar - Responsive Overlay/Sidebar */}
      {showDocs && (
        <div className="absolute inset-0 md:static md:w-80 bg-[#252526] border-l border-[#333] flex flex-col shadow-2xl z-20">
          <div className="p-3 bg-[#1e1e1e] border-b border-[#333] font-bold text-gray-400 text-xs uppercase tracking-wider flex justify-between items-center">
            <span>Документация</span>
            <button onClick={() => setShowDocs(false)} className="md:hidden text-gray-500 hover:text-white"><X size={16}/></button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-6 text-xs no-scrollbar">
            
            <section>
              <h3 className="text-blue-400 font-bold mb-2 text-sm flex items-center gap-2"><FileCode size={14}/> Методы</h3>
              <div className="space-y-3">
                <div>
                  <code className="block bg-[#333] p-1 rounded text-orange-300 mb-1">AddPanel(w, h, [th])</code>
                  <p className="text-gray-500">Создает деталь. th = 16 по умолч.</p>
                </div>
                <div>
                  <code className="block bg-[#333] p-1 rounded text-red-300 mb-1">DeleteAll()</code>
                  <p className="text-gray-500">Очищает сцену.</p>
                </div>
              </div>
            </section>

            <section>
              <h3 className="text-purple-400 font-bold mb-2 text-sm">Свойства Детали</h3>
              <div className="space-y-3">
                <div>
                  <code className="block bg-[#333] p-1 rounded text-yellow-300 mb-1">.setName(name)</code>
                  <p className="text-gray-400">Задать имя.</p>
                </div>
                <div>
                  <code className="block bg-[#333] p-1 rounded text-yellow-300 mb-1">.setPos(x, y, z)</code>
                  <p className="text-gray-400">Координаты.</p>
                </div>
                <div>
                  <code className="block bg-[#333] p-1 rounded text-yellow-300 mb-1">.setOrient(axis)</code>
                  <p className="text-gray-400">'X', 'Y', 'Z'.</p>
                </div>
                <div>
                  <code className="block bg-[#333] p-1 rounded text-yellow-300 mb-1">.setMaterial(id)</code>
                  <p className="text-gray-400">ID из библиотеки или 'HDF'.</p>
                </div>
                <div>
                  <code className="block bg-[#333] p-1 rounded text-yellow-300 mb-1">.addHardware(type, x, y)</code>
                  <p className="text-gray-400">Типы: screw, minifix_cam, shelf_support, handle.</p>
                </div>
                <div>
                  <code className="block bg-[#333] p-1 rounded text-yellow-300 mb-1">.addGroove(w, d, off, side)</code>
                  <p className="text-gray-400">Паз. side: 'top'|'bottom'...</p>
                </div>
              </div>
            </section>

          </div>
        </div>
      )}
    </div>
  );
};

export default ScriptEditor;
