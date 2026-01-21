import React from 'react';

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  label: string;
  icon?: React.ElementType;
}

export const TabButton: React.FC<TabButtonProps> = ({ active, onClick, label, icon: Icon }) => (
  <button 
    onClick={onClick}
    className={`flex-1 py-2 text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 transition-colors border-b-2 
    ${active ? 'border-blue-500 text-blue-400 bg-slate-800' : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'}`}
  >
    {Icon && <Icon size={14} />} {label}
  </button>
);

interface VisualSelectorProps {
  options: { id: string; label: string; icon: React.ElementType }[];
  value: string;
  onChange: (val: string) => void;
}

export const VisualSelector: React.FC<VisualSelectorProps> = ({ options, value, onChange }) => (
  <div className="grid grid-cols-3 gap-2">
    {options.map(opt => (
      <button
        key={opt.id}
        onClick={() => onChange(opt.id)}
        className={`flex flex-col items-center justify-center p-2 rounded-lg border transition-all ${value === opt.id 
          ? 'bg-blue-600/20 border-blue-500 text-white shadow-inner' 
          : 'bg-[#1a1a1a] border-[#333] text-slate-500 hover:border-slate-500 hover:text-slate-300'}`}
      >
        <opt.icon size={20} className="mb-1"/>
        <span className="text-[9px] font-bold uppercase">{opt.label}</span>
      </button>
    ))}
  </div>
);

interface ToolButtonProps {
  onClick: () => void;
  label: string;
  icon: React.ElementType;
  colorClass?: string;
  title?: string;
}

export const ToolButton: React.FC<ToolButtonProps> = ({ onClick, label, icon: Icon, colorClass = 'hover:bg-blue-600', title }) => (
  <button 
    onClick={onClick}
    className={`w-14 h-14 bg-[#333] rounded-xl flex flex-col items-center justify-center transition group relative border border-slate-700 ${colorClass}`}
    title={title || label}
  >
    <Icon size={22} className="text-slate-400 group-hover:text-white mb-1"/>
    <span className="text-[9px] text-slate-400 group-hover:text-white font-medium">{label}</span>
  </button>
);

export const MinusIcon = (props: any) => (
  <svg {...props} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
    <path d="M5 12h14" />
  </svg>
);

export const ArchiveBoxIcon = (props: any) => (
  <svg {...props} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <line x1="12" y1="10" x2="12" y2="12" strokeLinecap="round" strokeWidth="3" />
  </svg>
);

export const CircleIcon = (props: any) => (
  <svg {...props} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="8" />
  </svg>
);
