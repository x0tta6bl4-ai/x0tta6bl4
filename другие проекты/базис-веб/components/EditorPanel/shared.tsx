import React from 'react';

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  label: string;
}

export const TabButton: React.FC<TabButtonProps> = ({ active, onClick, label }) => (
  <button
    onClick={onClick}
    className={`flex-1 min-w-[70px] py-2 text-[9px] font-bold uppercase transition ${
      active
        ? 'text-blue-400 border-b border-blue-500'
        : 'text-slate-500 hover:text-slate-300'
    }`}
  >
    {label}
  </button>
);

interface GrooveSideButtonProps {
  side: 'top' | 'bottom' | 'left' | 'right';
  isActive: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  position: string;
}

export const GrooveSideButton: React.FC<GrooveSideButtonProps> = ({
  isActive,
  onClick,
  icon,
  position,
}) => (
  <button
    onClick={onClick}
    className={`absolute p-1 rounded-full border shadow-sm ${position} ${
      isActive
        ? 'bg-blue-500 border-blue-400 text-white'
        : 'bg-slate-800 border-slate-600 text-slate-400 hover:bg-slate-700'
    }`}
  >
    {icon}
  </button>
);

interface GrooveIndicatorProps {
  side?: 'top' | 'bottom' | 'left' | 'right';
}

export const GrooveIndicator: React.FC<GrooveIndicatorProps> = ({ side }) => {
  if (!side) return null;

  if (side === 'top' || side === 'bottom') {
    return (
      <div
        className={`absolute left-2 right-2 h-1 bg-blue-500/50 rounded-full animate-pulse ${
          side === 'top' ? 'top-1' : 'bottom-1'
        }`}
      />
    );
  }

  return (
    <div
      className={`absolute top-2 bottom-2 w-1 bg-blue-500/50 rounded-full animate-pulse ${
        side === 'left' ? 'left-1' : 'right-1'
      }`}
    />
  );
};

export const inputClass =
  'w-full mt-1.5 p-2 border border-slate-700 rounded-md text-xs bg-slate-800 text-slate-100 focus:ring-2 focus:ring-blue-500 outline-none transition font-mono';
export const labelClass =
  'text-[10px] font-bold text-slate-500 uppercase tracking-wider';
