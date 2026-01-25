
import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Save, FileCode, HelpCircle, FileJson, X } from 'lucide-react';

interface ScriptEditorProps {
  code: string;
  onChange: (code: string) => void;
  onRun: (code: string) => void;
}

const DEFAULT_SCRIPT = `// ============================================================================
// ЗАКАЗ: Шкаф-купе 1600х2400х600
// Материал: Egger W980 (Белый платиновый)
// Особенности: Деталировка ящиков (короб + фасад), отступы для купе
// ============================================================================

DeleteAll();

// --- КОНСТАНТЫ ---
const W = 1600;
const H = 2400;
const D = 600;
const BASE_H = 70;   // Цоколь
const COUPE_GAP = 100; // Место под двери (направляющие)
const MAT_BODY = 'eg-w980';
const MAT_BACK = 'eg-hdf';
const TH = 16; 

// --- 1. КОРПУС ---

// Боковины (Полная высота, глубина D)
// Кромка: Лицо 2мм, низ 0.4
const sideL = AddPanel(D, H, TH).setName('Бок Левый').setMaterial(MAT_BODY).setOrient('X').setPos(0, 0, 0).addEdging('front:2.0', 'bottom:0.4');
const sideR = AddPanel(D, H, TH).setName('Бок Правый').setMaterial(MAT_BODY).setOrient('X').setPos(W-TH, 0, 0).addEdging('front:2.0', 'bottom:0.4');

// Дно (на цоколе)
const botW = W - 2*TH;
const bottom = AddPanel(botW, D, TH).setName('Дно').setMaterial(MAT_BODY).setOrient('Y').setPos(TH, BASE_H, 0).addEdging('front:2.0');

// Крышка (Накладная для жесткости)
const roof = AddPanel(W, D, TH).setName('Крышка').setMaterial(MAT_BODY).setOrient('Y').setPos(0, H-TH, 0).addEdging('front:2.0', 'left:0.4', 'right:0.4');

// Цоколь (планки)
AddPanel(botW, BASE_H, TH).setName('Цоколь Перед').setMaterial(MAT_BODY).setOrient('Z').setPos(TH, 0, D-60);
AddPanel(botW, BASE_H, TH).setName('Цоколь Зад').setMaterial(MAT_BODY).setOrient('Z').setPos(TH, 0, 60);

// Задняя стенка (Накладная ХДФ) - упрощенно
AddPanel(W-4, H-BASE_H-20, 4).setName('Задняя стенка').setMaterial(MAT_BACK).setOrient('Z').setPos(2, BASE_H+2, 0);


// --- 2. ВНУТРЕННЕЕ НАПОЛНЕНИЕ ---

// Глубина внутренних деталей (минус двери купе)
const innerD = D - COUPE_GAP; 
// Ширина секции (половина минус стойка)
const sectionW = (botW - TH) / 2;

// Центральная стойка
const divX = TH + sectionW;
AddPanel(innerD, H - BASE_H - TH - TH, TH).setName('Стойка Центр').setMaterial(MAT_BODY).setOrient('X').setPos(divX, BASE_H+TH, 0).addEdging('front:2.0');

// ЛЕВАЯ СЕКЦИЯ (Полки)
const shelfW = sectionW;
const leftX = TH;
let sY = BASE_H + TH + 350;

for(let i=1; i<=5; i++) {
    AddPanel(shelfW, innerD, TH).setName('Полка Л-'+i).setMaterial(MAT_BODY).setOrient('Y')
        .setPos(leftX, sY, 0).addEdging('front:2.0')
        .addHardware('shelf_support', 0, 0);
    sY += 350;
}

// ПРАВАЯ СЕКЦИЯ (Антресоль, Штанга, Ящики)
const rightX = divX + TH;

// Антресольная полка
AddPanel(shelfW, innerD, TH).setName('Полка Антресоль').setMaterial(MAT_BODY).setOrient('Y')
    .setPos(rightX, H-400, 0).addEdging('front:2.0');

// Штанга (условно обозначена фурнитурой на боковинах)
sideR.addHardware('rod_holder', innerD/2, H-450);
// Добавляем держатель на стойку (в локальных координатах стойки это сложнее, добавим визуально штангу как цилиндр через API в будущем, пока фурнитура)

// --- 3. БЛОК ЯЩИКОВ (Правильный конструктив) ---

// Крышка блока ящиков
const drawerTopY = BASE_H + TH + 700; 
AddPanel(shelfW, innerD, TH).setName('Крышка Ящиков').setMaterial(MAT_BODY).setOrient('Y')
    .setPos(rightX, drawerTopY, 0).addEdging('front:2.0');

// Генерация 3-х ящиков
const drawerCount = 3;
const drawerTotalH = 700; // Общая высота зоны ящиков
const facadeH = (drawerTotalH - 20) / drawerCount - 4; // Высота фасада (с зазорами)
let currentY = BASE_H + TH + 10; // Отступ снизу

for(let k=1; k<=drawerCount; k++) {
    createDrawerBox(rightX, currentY, sectionW, facadeH, innerD, k);
    currentY += facadeH + 4; // Шаг с зазором
}

// ФУНКЦИЯ СОЗДАНИЯ ЯЩИКА (Короб + Фасад)
function createDrawerBox(x, y, w, h, maxD, index) {
    const gapSide = 13; // Зазор под направляющие
    const boxH = 140;   // Высота боковины ящика
    const boxD = 450;   // Глубина ящика (стандарт направляющей)
    
    // 1. Фасад (Внутренний, вкладной относительно дверей купе, но накладной на короб)
    // Позиция Z фасада: углублен относительно торца стойки, чтобы не бить в двери
    const facadeZ = maxD - 20; 
    
    // Внутренний фасад обычно входит МЕЖДУ стойками с зазором 2мм
    const fW = w - 4; // Зазор по 2мм слева и справа
    const fX = x + 2;
    
    AddPanel(fW, h, TH).setName('Фасад Ящ.'+index).setMaterial(MAT_BODY).setOrient('Z')
        .setPos(fX, y, facadeZ).addEdging('all:2.0')
        .setOpening('drawer') // Для анимации
        .addHardware('handle', fW/2, h/2);

    // 2. Короб Ящика (Боковины, Лоб, Зад)
    // Корпус ящика смещен назад от фасада (обычно фасад прикручивается к "лбу" ящика)
    const boxZ_Start = facadeZ - TH; // Сразу за фасадом
    
    // Позиция короба по X (центруем)
    const boxW = w - (gapSide * 2); // Ширина короба
    const boxX = x + gapSide;
    const boxY = y + (h - boxH)/2; // Центруем короб по высоте фасада
    
    // Боковины ящика (вкладные между передом и задом или накладные? Стандарт: бока на всю глубину 450)
    // Бок Л
    AddPanel(boxD, boxH, TH).setName('Ящик Бок Л').setMaterial(MAT_BODY).setOrient('X')
        .setPos(boxX, boxY, boxZ_Start - boxD).addEdging('top:0.4')
        .setOpening('drawer'); // Привязка к анимации
        
    // Бок П
    AddPanel(boxD, boxH, TH).setName('Ящик Бок П').setMaterial(MAT_BODY).setOrient('X')
        .setPos(boxX + boxW - TH, boxY, boxZ_Start - boxD).addEdging('top:0.4')
        .setOpening('drawer');

    // Лоб и Зад (вкладные между боками)
    const frontBackW = boxW - 2*TH;
    
    // Лоб (к нему крепится фасад)
    AddPanel(frontBackW, boxH, TH).setName('Ящик Лоб').setMaterial(MAT_BODY).setOrient('Z')
        .setPos(boxX + TH, boxY, boxZ_Start).addEdging('top:0.4')
        .setOpening('drawer');
        
    // Задняя стенка ящика
    AddPanel(frontBackW, boxH, TH).setName('Ящик Зад').setMaterial(MAT_BODY).setOrient('Z')
        .setPos(boxX + TH, boxY, boxZ_Start - boxD + TH).addEdging('top:0.4')
        .setOpening('drawer');
        
    // Дно ящика (ХДФ накладное снизу или в паз, тут упрощенно накладное)
    // Размеры дна = габарит короба
    AddPanel(boxW, boxD, 4).setName('Дно Ящика').setMaterial(MAT_BACK).setOrient('Y')
        .setPos(boxX, boxY, boxZ_Start - boxD).setOpening('drawer');
        
    // Направляющие (фурнитура на боковины шкафа)
    // Условно добавляем на правую стойку и боковину
    // (В реальном скрипте нужно добавлять hardware к родительским панелям)
}

alert('Готово: Шкаф-купе с ящиками и фурнитурой');
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
