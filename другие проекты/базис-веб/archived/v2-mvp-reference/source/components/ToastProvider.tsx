
import React from 'react';
import { useProjectStore } from '../store/projectStore';
import { CheckCircle, Info, XCircle, X } from 'lucide-react';

const ToastProvider: React.FC = () => {
  const { toasts, removeToast } = useProjectStore();

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border backdrop-blur-md animate-in slide-in-from-right-full transition-all duration-300
            ${toast.type === 'success' ? 'bg-emerald-900/90 border-emerald-500/30 text-emerald-100' : ''}
            ${toast.type === 'error' ? 'bg-red-900/90 border-red-500/30 text-red-100' : ''}
            ${toast.type === 'info' ? 'bg-slate-800/90 border-slate-600/30 text-slate-100' : ''}
          `}
        >
          {toast.type === 'success' && <CheckCircle size={18} className="text-emerald-400" />}
          {toast.type === 'error' && <XCircle size={18} className="text-red-400" />}
          {toast.type === 'info' && <Info size={18} className="text-blue-400" />}
          
          <span className="text-sm font-medium">{toast.message}</span>
          
          <button onClick={() => removeToast(toast.id)} className="ml-2 opacity-50 hover:opacity-100">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
};

export default ToastProvider;
