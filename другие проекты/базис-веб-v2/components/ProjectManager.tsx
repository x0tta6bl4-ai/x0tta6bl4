
import React, { useRef } from 'react';
import { useCabinet } from './CabinetContext';
import { Save, FolderOpen, Download, Upload } from 'lucide-react';

export const ProjectManager: React.FC = () => {
  const { params, updateParams } = useCabinet();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSave = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(params, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", `project_${params.name || 'cabinet'}_${Date.now()}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  };

  const handleLoad = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = JSON.parse(event.target?.result as string);
        if (json && typeof json === 'object') {
            // Basic validation
            updateParams(json);
        } else {
            alert('Неверный формат файла');
        }
      } catch (err) {
        console.error(err);
        alert('Ошибка чтения файла');
      }
      // Reset input
      if(fileInputRef.current) fileInputRef.current.value = '';
    };
    reader.readAsText(file);
  };

  return (
    <div className="flex gap-2">
      <button 
        onClick={handleSave}
        className="flex items-center gap-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded border border-slate-700 transition"
        title="Скачать JSON"
      >
        <Save size={14} /> <span>Сохранить</span>
      </button>
      
      <button 
        onClick={() => fileInputRef.current?.click()}
        className="flex items-center gap-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded border border-slate-700 transition"
        title="Загрузить JSON"
      >
        <FolderOpen size={14} /> <span>Загрузить</span>
      </button>
      <input 
        type="file" 
        ref={fileInputRef} 
        onChange={handleLoad} 
        className="hidden" 
        accept=".json"
      />
    </div>
  );
};
