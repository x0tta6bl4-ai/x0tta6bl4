
import React, { useState } from 'react';
import { useProjectStore } from '../store/projectStore';
import { DxfExporter } from '../services/DxfExporter';
import { FileDown, Table, X, Download, FileJson } from 'lucide-react';

export const ExportPanel: React.FC = () => {
  const { panels } = useProjectStore();
  const [isOpen, setIsOpen] = useState(false);

  // Generate a project name based on date/content
  const projectName = `project_${new Date().toLocaleDateString().replace(/\//g, '-')}`;

  const handleExportDXF = () => {
    const dxf = DxfExporter.export(panels);
    downloadFile(dxf, `${projectName}.dxf`, 'application/dxf');
  };

  const handleExportCSV = () => {
    let csv = "Name;Length;Width;Thickness;Material;Qty\n";
    panels.forEach(p => {
        csv += `${p.name};${p.width};${p.height};${p.depth};${p.materialId};1\n`;
    });
    downloadFile(csv, `${projectName}_cutlist.csv`, 'text/csv');
  };

  const handleExportJSON = () => {
      const projectData = {
          version: "1.0",
          timestamp: Date.now(),
          panels: panels
      };
      const json = JSON.stringify(projectData, null, 2);
      downloadFile(json, `${projectName}.json`, 'application/json');
  };

  const downloadFile = (content: string, filename: string, type: string) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (panels.length === 0) return null;

  return (
    <div className="fixed bottom-20 right-6 z-40 flex flex-col items-end gap-3 pointer-events-none">
        
        {/* Menu Items */}
        <div className={`flex flex-col items-end gap-2 transition-all duration-300 ${isOpen ? 'opacity-100 translate-y-0 pointer-events-auto' : 'opacity-0 translate-y-10 pointer-events-none'}`}>
            
            <button onClick={handleExportDXF} className="flex items-center gap-2 px-4 py-2 bg-white text-slate-800 rounded-full shadow-lg hover:bg-blue-50 transition border border-slate-200">
                <span className="text-xs font-bold">Скачать DXF</span>
                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600"><FileDown size={16}/></div>
            </button>

            <button onClick={handleExportCSV} className="flex items-center gap-2 px-4 py-2 bg-white text-slate-800 rounded-full shadow-lg hover:bg-green-50 transition border border-slate-200">
                <span className="text-xs font-bold">Смета (CSV)</span>
                <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center text-green-600"><Table size={16}/></div>
            </button>

            <button onClick={handleExportJSON} className="flex items-center gap-2 px-4 py-2 bg-white text-slate-800 rounded-full shadow-lg hover:bg-orange-50 transition border border-slate-200">
                <span className="text-xs font-bold">Проект JSON</span>
                <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center text-orange-600"><FileJson size={16}/></div>
            </button>

        </div>

        {/* FAB Toggle */}
        <button 
            onClick={() => setIsOpen(!isOpen)}
            className={`w-14 h-14 rounded-full shadow-xl flex items-center justify-center text-white transition-all transform hover:scale-105 active:scale-95 pointer-events-auto
                ${isOpen ? 'bg-slate-700 rotate-45' : 'bg-blue-600 hover:bg-blue-500'}`}
            title="Экспорт"
        >
            {isOpen ? <X size={24}/> : <Download size={24}/>}
        </button>
    </div>
  );
};
