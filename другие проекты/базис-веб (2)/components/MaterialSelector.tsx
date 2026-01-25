
import React, { useState, useMemo } from 'react';
import { useCabinet } from './CabinetContext';
import { MATERIAL_LIBRARY } from '../data/materials';
import { Material, MaterialCategory } from '../types';
import { Check, Search, Star, Filter, Heart, Info } from 'lucide-react';

const CATEGORIES: { id: MaterialCategory | 'all', label: string }[] = [
    { id: 'all', label: 'Все' },
    { id: 'ldsp', label: 'ЛДСП' },
    { id: 'wood', label: 'Массив' },
    { id: 'plastic', label: 'Пластик' },
    { id: 'glass', label: 'Стекло' },
];

export const MaterialSelector: React.FC = () => {
  const { params, setMaterial } = useCabinet();
  const [activeCategory, setActiveCategory] = useState<MaterialCategory | 'all'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [favorites, setFavorites] = useState<string[]>([]);
  const [showOnlyFavs, setShowOnlyFavs] = useState(false);

  // Load favorites from local storage on mount (simplified for this component)
  React.useEffect(() => {
      const stored = localStorage.getItem('bazis_fav_materials');
      if (stored) {
          try { setFavorites(JSON.parse(stored)); } catch (e) { /* ignore */ }
      }
  }, []);

  const toggleFavorite = (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      const newFavs = favorites.includes(id) 
          ? favorites.filter(fid => fid !== id) 
          : [...favorites, id];
      setFavorites(newFavs);
      localStorage.setItem('bazis_fav_materials', JSON.stringify(newFavs));
  };

  const filteredMaterials = useMemo(() => {
      return MATERIAL_LIBRARY.filter(mat => {
          // 1. Category Filter
          if (activeCategory !== 'all' && mat.category !== activeCategory) return false;
          
          // 2. Search Filter
          if (searchTerm && !mat.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
          
          // 3. Favorites Filter
          if (showOnlyFavs && !favorites.includes(mat.id)) return false;

          return true;
      });
  }, [activeCategory, searchTerm, showOnlyFavs, favorites]);

  // Determine current active material object for checking
  // Note: params.material stores the ID or name. We need to match it.
  // In the legacy system it stored a simple name like "Белый". 
  // We need to support both legacy short names and new IDs.
  const isSelected = (mat: Material) => {
      // Legacy compatibility check
      if (['Белый', 'Дуб', 'Графит', 'Бетон'].includes(params.material as any)) {
          if (params.material === 'Белый' && mat.id === 'eg-w980') return true;
          if (params.material === 'Дуб' && mat.id === 'eg-h1145') return true;
          if (params.material === 'Графит' && mat.id === 'ks-0191') return true;
          if (params.material === 'Бетон' && mat.id === 'eg-f186') return true;
          return false;
      }
      return params.material === mat.id; // Correct check for new system
  };

  return (
    <div className="space-y-3 bg-[#1a1a1a] p-3 rounded-lg border border-slate-700">
      <div className="flex justify-between items-center">
          <label className="text-xs font-bold text-slate-400 uppercase flex items-center gap-2">
              <Filter size={12}/> Библиотека Материалов
          </label>
          <div className="text-[10px] text-slate-500">{filteredMaterials.length} шт.</div>
      </div>

      {/* Tools */}
      <div className="flex gap-2">
          <div className="relative flex-1">
              <Search className="absolute left-2 top-2 text-slate-500" size={12}/>
              <input 
                  type="text" 
                  placeholder="Поиск..." 
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full bg-[#111] border border-slate-600 rounded pl-7 pr-2 py-1.5 text-xs text-white focus:border-blue-500 outline-none"
              />
          </div>
          <button 
              onClick={() => setShowOnlyFavs(!showOnlyFavs)}
              className={`p-1.5 rounded border transition ${showOnlyFavs ? 'bg-amber-900/30 border-amber-500 text-amber-400' : 'bg-[#222] border-slate-600 text-slate-500'}`}
              title="Только избранное"
          >
              <Star size={14} fill={showOnlyFavs ? "currentColor" : "none"}/>
          </button>
      </div>

      {/* Categories */}
      <div className="flex gap-1 overflow-x-auto no-scrollbar pb-1">
          {CATEGORIES.map(cat => (
              <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={`px-3 py-1 text-[10px] font-bold uppercase rounded-full whitespace-nowrap transition border ${activeCategory === cat.id ? 'bg-blue-600 text-white border-blue-500' : 'bg-[#222] text-slate-400 border-slate-700 hover:border-slate-500'}`}
              >
                  {cat.label}
              </button>
          ))}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 gap-2 max-h-60 overflow-y-auto no-scrollbar pr-1">
        {filteredMaterials.map((mat) => {
            const active = isSelected(mat);
            return (
              <button
                key={mat.id}
                onClick={() => setMaterial(mat.id as any)} // Cast to compatibility type
                className={`relative flex flex-col items-start p-2 rounded-lg border transition-all text-left group overflow-hidden
                  ${active 
                    ? 'border-blue-500 bg-blue-900/20 ring-1 ring-blue-500/50' 
                    : 'border-slate-700 bg-[#222] hover:border-slate-500 hover:bg-[#2a2a2a]'
                  }`}
              >
                {/* Visual Preview */}
                <div className="w-full aspect-video rounded mb-2 overflow-hidden relative bg-gray-800 border border-black/20">
                    {/* Fallback color or texture */}
                    <div 
                        className="w-full h-full" 
                        style={{ backgroundColor: mat.color }} 
                    />
                    {/* Gradient Overlay for sheen effect */}
                    <div className="absolute inset-0 bg-gradient-to-tr from-black/20 to-white/10 pointer-events-none"></div>
                    
                    {/* Fav Button */}
                    <div 
                        onClick={(e) => toggleFavorite(mat.id, e)}
                        className={`absolute top-1 right-1 p-1 rounded-full bg-black/40 backdrop-blur hover:bg-black/60 transition ${favorites.includes(mat.id) ? 'text-amber-400' : 'text-slate-400 opacity-0 group-hover:opacity-100'}`}
                    >
                        <Heart size={10} fill={favorites.includes(mat.id) ? "currentColor" : "none"}/>
                    </div>
                </div>

                <div className="w-full">
                    <div className="flex justify-between items-start">
                        <div className="text-[10px] font-bold text-slate-200 line-clamp-1" title={mat.name}>{mat.name}</div>
                        {active && <Check size={12} className="text-blue-500 shrink-0 ml-1"/>}
                    </div>
                    <div className="flex justify-between items-center mt-1 text-[9px] text-slate-500">
                        <span className="font-mono">{mat.thickness}мм</span>
                        <span>{mat.pricePerM2} ₽</span>
                    </div>
                </div>
                
                {/* Hover Info */}
                <div className="absolute inset-0 bg-black/80 flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none p-2 text-center">
                    <span className="text-[10px] text-slate-300 font-bold">{mat.brand}</span>
                    <span className="text-[9px] text-slate-500">{mat.article}</span>
                </div>
              </button>
            );
        })}
      </div>
    </div>
  );
};
