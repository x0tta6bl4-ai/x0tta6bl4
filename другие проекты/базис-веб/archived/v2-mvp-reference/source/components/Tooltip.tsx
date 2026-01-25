
import React, { useState, useRef, useEffect } from 'react';

interface TooltipProps {
  content: string;
  children: React.ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
  delay?: number;
}

export const Tooltip: React.FC<TooltipProps> = ({ content, children, position = 'top', delay = 300 }) => {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = () => {
    timeoutRef.current = setTimeout(() => setVisible(true), delay);
  };

  const hide = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setVisible(false);
  };

  useEffect(() => {
      return () => {
          if (timeoutRef.current) clearTimeout(timeoutRef.current);
      };
  }, []);

  const posClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  return (
    <div 
      className="relative flex items-center justify-center group" 
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {visible && (
        <div className={`absolute z-[100] px-2 py-1.5 text-xs font-medium text-white bg-slate-900 border border-slate-700 rounded-md shadow-xl whitespace-nowrap pointer-events-none animate-in fade-in zoom-in-95 duration-200 ${posClasses[position]}`}>
          {content}
          {/* Arrow */}
          <div className={`absolute w-2 h-2 bg-slate-900 border-slate-700 transform rotate-45 
            ${position === 'top' ? 'bottom-[-5px] left-1/2 -translate-x-1/2 border-r border-b' : ''}
            ${position === 'bottom' ? 'top-[-5px] left-1/2 -translate-x-1/2 border-l border-t' : ''}
            ${position === 'left' ? 'right-[-5px] top-1/2 -translate-y-1/2 border-r border-t' : ''}
            ${position === 'right' ? 'left-[-5px] top-1/2 -translate-y-1/2 border-l border-b' : ''}
          `} />
        </div>
      )}
    </div>
  );
};
