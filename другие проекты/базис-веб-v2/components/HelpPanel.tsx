
import React, { useState } from 'react';
import { X, Keyboard, Youtube, HelpCircle, Search, FileText } from 'lucide-react';

interface HelpPanelProps {
  onClose: () => void;
}

export const HelpPanel: React.FC<HelpPanelProps> = ({ onClose }) => {
  const [activeTab, setActiveTab] = useState<'shortcuts' | 'faq' | 'video'>('shortcuts');
  const [search, setSearch] = useState('');

  const shortcuts = [
      { key: 'Ctrl + Z', desc: 'Отменить действие' },
      { key: 'Ctrl + Y', desc: 'Повторить действие' },
      { key: 'Ctrl + S', desc: 'Сохранить проект' },
      { key: 'Space', desc: 'Вращать камеру (в 3D)' },
      { key: 'Delete', desc: 'Удалить выделенное' },
  ];

  const faqs = [
      { q: 'Как добавить полку?', a: 'В режиме "Мастер" нажмите кнопку "Полка" или перетащите полку в список.' },
      { q: 'Как изменить размер?', a: 'В режиме "Конструктор" выберите деталь и измените параметры в панели справа.' },
      { q: 'Как скачать DXF?', a: 'Нажмите кнопку экспорта (иконка скачивания) в углу 3D вида.' },
      { q: 'Что означают цвета на схеме?', a: 'Красный - кромка 2мм, Синий - кромка 0.4мм.' },
  ];

  const filteredFaqs = faqs.filter(f => f.q.toLowerCase().includes(search.toLowerCase()) || f.a.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#1e1e1e] w-full max-w-2xl h-[600px] rounded-2xl border border-slate-700 flex flex-col shadow-2xl overflow-hidden">
        <div className="p-4 border-b border-slate-700 flex justify-between items-center bg-[#252526]">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <HelpCircle className="text-blue-500" /> Справка и Обучение
            </h2>
            <button onClick={onClose} className="p-2 hover:bg-slate-700 rounded-full text-slate-400 hover:text-white transition">
                <X size={20} />
            </button>
        </div>

        <div className="flex border-b border-slate-700 bg-[#222]">
            <button onClick={() => setActiveTab('shortcuts')} className={`flex-1 py-3 text-sm font-bold transition ${activeTab === 'shortcuts' ? 'text-blue-400 border-b-2 border-blue-500' : 'text-slate-500 hover:text-white'}`}>Горячие клавиши</button>
            <button onClick={() => setActiveTab('faq')} className={`flex-1 py-3 text-sm font-bold transition ${activeTab === 'faq' ? 'text-blue-400 border-b-2 border-blue-500' : 'text-slate-500 hover:text-white'}`}>FAQ</button>
            <button onClick={() => setActiveTab('video')} className={`flex-1 py-3 text-sm font-bold transition ${activeTab === 'video' ? 'text-blue-400 border-b-2 border-blue-500' : 'text-slate-500 hover:text-white'}`}>Видеоуроки</button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 bg-[#111]">
            {activeTab === 'shortcuts' && (
                <div className="space-y-4">
                    <h3 className="text-slate-400 text-xs font-bold uppercase mb-4 flex items-center gap-2"><Keyboard size={16}/> Клавиатура</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {shortcuts.map((s, i) => (
                            <div key={i} className="flex justify-between items-center bg-[#252526] p-3 rounded border border-slate-700">
                                <span className="text-slate-300 text-sm">{s.desc}</span>
                                <kbd className="bg-slate-800 px-2 py-1 rounded text-xs font-mono text-white border border-slate-600">{s.key}</kbd>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {activeTab === 'faq' && (
                <div className="space-y-4">
                    <div className="relative mb-4">
                        <Search className="absolute left-3 top-2.5 text-slate-500" size={16}/>
                        <input 
                            type="text" 
                            placeholder="Поиск по справке..." 
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="w-full bg-[#252526] border border-slate-700 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:border-blue-500 outline-none"
                        />
                    </div>
                    {filteredFaqs.map((f, i) => (
                        <div key={i} className="bg-[#252526] p-4 rounded border border-slate-700">
                            <h4 className="font-bold text-white mb-2 flex items-center gap-2"><HelpCircle size={14} className="text-blue-500"/> {f.q}</h4>
                            <p className="text-slate-400 text-sm">{f.a}</p>
                        </div>
                    ))}
                </div>
            )}

            {activeTab === 'video' && (
                <div className="flex flex-col items-center justify-center h-full text-slate-500">
                    <Youtube size={64} className="mb-4 opacity-50"/>
                    <p>Видеоуроки скоро будут добавлены</p>
                </div>
            )}
        </div>
      </div>
    </div>
  );
};
