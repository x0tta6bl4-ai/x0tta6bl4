
import React, { useState } from 'react';
import { CabinetConfig, Section, CabinetItem } from '../types';
import { LayoutDashboard, Utensils, Warehouse, X, ArrowRight, Check, Box } from 'lucide-react';

interface TemplateSelectorProps {
  onSelect: (template: { config: CabinetConfig; sections: Section[] }) => void;
  onClose: () => void;
}

interface DesignTemplate {
  id: string;
  name: string;
  category: 'wardrobe' | 'kitchen' | 'office';
  description: string;
  thumbnail: string;
  tags: string[];
  config: CabinetConfig;
  sections: Section[];
}

const TEMPLATES: DesignTemplate[] = [
  {
    id: 'wardrobe-2door-std',
    name: 'Шкаф-купе 2-дверный',
    category: 'wardrobe',
    description: 'Классический шкаф-купе с полками и штангой. Оптимален для спальни.',
    thumbnail: '🚪',
    tags: ['Стандарт', 'Популярное'],
    config: {
      name: 'Шкаф-купе', type: 'straight', width: 1600, height: 2400, depth: 600,
      doorType: 'sliding', doorCount: 2, baseType: 'plinth', facadeStyle: 'solid',
      construction: 'corpus', backType: 'groove', hardwareType: 'confirmat',
      doorGap: 2, coupeGap: 26,
      material: 'Белый', shelves: [], drawers: []
    },
    sections: [
      { id: 1, width: 784, items: [
          { id: '1-1', type: 'shelf', name: 'Полка', y: 2000, height: 16 },
          { id: '1-2', type: 'rod', name: 'Штанга', y: 1900, height: 16 },
          { id: '1-3', type: 'shelf', name: 'Полка', y: 400, height: 16 }
      ]},
      { id: 2, width: 784, items: [
          { id: '2-1', type: 'shelf', name: 'Полка', y: 2000, height: 16 },
          { id: '2-2', type: 'shelf', name: 'Полка', y: 1600, height: 16 },
          { id: '2-3', type: 'shelf', name: 'Полка', y: 1200, height: 16 },
          { id: '2-4', type: 'drawer', name: 'Ящик', y: 800, height: 176 },
          { id: '2-5', type: 'drawer', name: 'Ящик', y: 600, height: 176 },
          { id: '2-6', type: 'shelf', name: 'Полка', y: 300, height: 16 }
      ]}
    ]
  },
  {
    id: 'wardrobe-organizer-pro',
    name: 'Гардеробная PRO',
    category: 'wardrobe',
    description: 'Комплексная система хранения с ящиками, корзинами, пантографом и хоз. блоком.',
    thumbnail: '👑',
    tags: ['Премиум', 'Хоз. блок'],
    config: {
      name: 'Гардеробная', type: 'straight', width: 3200, height: 2500, depth: 600,
      doorType: 'none', doorCount: 0, baseType: 'plinth', facadeStyle: 'combined',
      construction: 'corpus', backType: 'groove', hardwareType: 'minifix',
      doorGap: 2, coupeGap: 26,
      material: 'Белый', shelves: [], drawers: []
    },
    sections: [
        { id: 1, width: 776, items: [
            { id: '1-1', type: 'shelf', name: 'Полка', y: 2150, height: 16 },
            { id: '1-2', type: 'rod', name: 'Штанга', y: 1950, height: 16 },
            { id: '1-3', type: 'basket', name: 'Корзина', y: 400, height: 160 },
            { id: '1-4', type: 'basket', name: 'Корзина', y: 150, height: 160 }
        ]},
        { id: 2, width: 776, items: [
            { id: '2-1', type: 'shelf', name: 'Полка', y: 2150, height: 16 },
            { id: '2-2', type: 'pantograph', name: 'Пантограф', y: 2000, height: 16 },
            { id: '2-3', type: 'shelf', name: 'Полка', y: 900, height: 16 },
            { id: '2-4', type: 'basket', name: 'Корзина', y: 400, height: 160 }
        ]},
        { id: 3, width: 776, items: [
            { id: '3-1', type: 'shelf', name: 'Полка', y: 2150, height: 16 },
            { id: '3-2', type: 'shelf', name: 'Полка', y: 1600, height: 16 },
            { id: '3-3', type: 'shelf', name: 'Полка', y: 1250, height: 16 },
            { id: '3-4', type: 'drawer', name: 'Ящик', y: 900, height: 176 },
            { id: '3-5', type: 'drawer', name: 'Ящик', y: 700, height: 176 },
            { id: '3-6', type: 'drawer', name: 'Ящик', y: 500, height: 176 },
            { id: '3-7', type: 'shoe_rack', name: 'Обувница', y: 200, height: 16 }
        ]},
        { id: 4, width: 776, items: [
            { id: '4-1', type: 'shelf', name: 'Полка', y: 2150, height: 16 },
            { id: '4-2', type: 'partition', name: 'Перегородка', y: 100, height: 1400 },
            { id: '4-3', type: 'shelf', name: 'Полка (узкая)', y: 1500, height: 16 },
            { id: '4-4', type: 'shelf', name: 'Полка (узкая)', y: 1200, height: 16 }, 
            { id: '4-5', type: 'shelf', name: 'Полка (узкая)', y: 900, height: 16 }
        ]}
    ]
  },
  {
    id: 'wardrobe-3door-big',
    name: 'Гардероб 3-дверный',
    category: 'wardrobe',
    description: 'Вместительный шкаф с распашными фасадами и антресолью.',
    thumbnail: '👔',
    tags: ['Большой', 'Распашной'],
    config: {
      name: 'Гардероб', type: 'straight', width: 2400, height: 2600, depth: 550,
      doorType: 'hinged', doorCount: 3, baseType: 'plinth', facadeStyle: 'solid',
      construction: 'corpus', backType: 'groove', hardwareType: 'confirmat',
      doorGap: 2, coupeGap: 26,
      material: 'Белый', shelves: [], drawers: []
    },
    sections: [
        { id: 1, width: 778, items: [{id:'1-1', type:'shelf', name: 'Полка', y:2100, height:16}, {id:'1-2', type:'rod', name: 'Штанга', y:2000, height:16}] },
        { id: 2, width: 778, items: [{id:'2-1', type:'shelf', name: 'Полка', y:2100, height:16}, {id:'2-2', type:'shelf', name: 'Полка', y:1700, height:16}, {id:'2-3', type:'shelf', name: 'Полка', y:1300, height:16}, {id:'2-4', type:'shelf', name: 'Полка', y:900, height:16}] },
        { id: 3, width: 778, items: [{id:'3-1', type:'shelf', name: 'Полка', y:2100, height:16}, {id:'3-2', type:'rod', name: 'Штанга', y:2000, height:16}] }
    ]
  },
  {
    id: 'kitchen-base-600',
    name: 'Кухонный стол 600',
    category: 'kitchen',
    description: 'Стандартный нижний модуль под мойку или хранение.',
    thumbnail: '🍽️',
    tags: ['Кухня', 'Модуль'],
    config: {
      name: 'Стол 600', type: 'straight', width: 600, height: 820, depth: 560,
      doorType: 'hinged', doorCount: 1, baseType: 'legs', facadeStyle: 'solid',
      construction: 'corpus', backType: 'overlay', hardwareType: 'confirmat',
      doorGap: 2, coupeGap: 26,
      material: 'Белый', shelves: [], drawers: []
    },
    sections: [
        { id: 1, width: 568, items: [{id:'1-1', type:'shelf', name: 'Полка', y:400, height:16}] }
    ]
  },
  {
    id: 'dresser-4-drawers',
    name: 'Комод 4 ящика',
    category: 'wardrobe',
    description: 'Комод бельевой на 4 выдвижных ящика.',
    thumbnail: '🗄️',
    tags: ['Спальня', 'Ящики'],
    config: {
      name: 'Комод', type: 'straight', width: 900, height: 900, depth: 450,
      doorType: 'none', doorCount: 0, baseType: 'plinth', facadeStyle: 'solid',
      construction: 'corpus', backType: 'overlay', hardwareType: 'confirmat',
      doorGap: 2, coupeGap: 26,
      material: 'Белый', shelves: [], drawers: []
    },
    sections: [
        { id: 1, width: 868, items: [
            {id:'1-1', type:'drawer', name: 'Ящик', y:780, height:176},
            {id:'1-2', type:'drawer', name: 'Ящик', y:580, height:176},
            {id:'1-3', type:'drawer', name: 'Ящик', y:380, height:176},
            {id:'1-4', type:'drawer', name: 'Ящик', y:180, height:176}
        ]}
    ]
  },
  {
    id: 'office-shelving',
    name: 'Стеллаж офисный',
    category: 'office',
    description: 'Открытый стеллаж для документов.',
    thumbnail: '📚',
    tags: ['Офис', 'Открытый'],
    config: {
      name: 'Стеллаж', type: 'straight', width: 800, height: 2000, depth: 350,
      doorType: 'none', doorCount: 0, baseType: 'plinth', facadeStyle: 'solid',
      construction: 'corpus', backType: 'overlay', hardwareType: 'confirmat',
      doorGap: 2, coupeGap: 26,
      material: 'Белый', shelves: [], drawers: []
    },
    sections: [
        { id: 1, width: 768, items: [
            {id:'1-1', type:'shelf', name: 'Полка', y:1650, height:16},
            {id:'1-2', type:'shelf', name: 'Полка', y:1300, height:16},
            {id:'1-3', type:'shelf', name: 'Полка', y:950, height:16},
            {id:'1-4', type:'shelf', name: 'Полка', y:600, height:16},
            {id:'1-5', type:'shelf', name: 'Полка', y:250, height:16}
        ]}
    ]
  }
];

const CATEGORIES = [
    { id: 'all', label: 'Все', icon: LayoutDashboard },
    { id: 'wardrobe', label: 'Шкафы', icon: Warehouse },
    { id: 'kitchen', label: 'Кухни', icon: Utensils },
    { id: 'office', label: 'Офис', icon: Box },
];

const TemplateSelector: React.FC<TemplateSelectorProps> = ({ onSelect, onClose }) => {
  const [activeCategory, setActiveCategory] = useState<string>('all');

  const filteredTemplates = activeCategory === 'all' 
    ? TEMPLATES 
    : TEMPLATES.filter(t => t.category === activeCategory);

  return (
    <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#1e1e1e] w-full max-w-5xl h-[80vh] rounded-2xl border border-slate-700 flex flex-col shadow-2xl overflow-hidden">
        
        {/* Header */}
        <div className="p-6 border-b border-slate-700 flex justify-between items-center bg-[#252526]">
            <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <LayoutDashboard className="text-blue-500" aria-hidden="true" /> Библиотека Шаблонов
                </h2>
                <p className="text-xs text-slate-400 mt-1">Выберите готовый проект для начала работы</p>
            </div>
            <button onClick={onClose} aria-label="Закрыть библиотеку шаблонов" className="p-2 hover:bg-slate-700 rounded-full text-slate-400 hover:text-white transition">
                <X size={20} />
            </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
            {/* Sidebar */}
            <div className="w-48 bg-[#252526] border-r border-slate-700 p-4 flex flex-col gap-2">
                {CATEGORIES.map(cat => (
                    <button
                        key={cat.id}
                        onClick={() => setActiveCategory(cat.id)}
                        className={`text-left px-4 py-3 rounded-lg flex items-center gap-3 transition font-medium text-sm
                            ${activeCategory === cat.id ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-700 hover:text-white'}
                        `}
                    >
                        <cat.icon size={16} /> {cat.label}
                    </button>
                ))}
            </div>

            {/* Grid */}
            <div className="flex-1 bg-[#111] p-6 overflow-y-auto no-scrollbar">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredTemplates.map(template => (
                        <div key={template.id} className="bg-[#252526] border border-slate-700 rounded-xl overflow-hidden group hover:border-blue-500 transition-all hover:shadow-xl hover:-translate-y-1">
                            <div className="h-32 bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center text-6xl relative">
                                {template.thumbnail}
                                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                                    <button 
                                        onClick={() => onSelect({ config: template.config, sections: template.sections })}
                                        className="bg-blue-600 text-white px-6 py-2 rounded-full font-bold text-sm transform scale-90 group-hover:scale-100 transition flex items-center gap-2"
                                    >
                                        Выбрать <ArrowRight size={16}/>
                                    </button>
                                </div>
                            </div>
                            <div className="p-4">
                                <div className="flex justify-between items-start mb-2">
                                    <h3 className="font-bold text-white text-base">{template.name}</h3>
                                </div>
                                <p className="text-xs text-slate-400 mb-4 line-clamp-2 h-8">{template.description}</p>
                                <div className="flex flex-wrap gap-2">
                                    {template.tags.map(tag => (
                                        <span key={tag} className="px-2 py-1 bg-slate-800 text-slate-400 text-[10px] rounded border border-slate-700">
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>

      </div>
    </div>
  );
};

export default TemplateSelector;
