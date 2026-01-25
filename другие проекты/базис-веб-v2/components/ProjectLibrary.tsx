
import React, { useEffect, useState } from 'react';
import { ProjectSnapshot } from '../types';
import { storageService } from '../services/storageService';
import { FolderOpen, Trash2, Clock, FileBox, Layout, Download } from 'lucide-react';

interface ProjectLibraryProps {
    onLoad: (project: ProjectSnapshot) => void;
    onClose: () => void;
}

const ProjectLibrary: React.FC<ProjectLibraryProps> = ({ onLoad, onClose }) => {
    const [projects, setProjects] = useState<ProjectSnapshot[]>([]);
    const [loading, setLoading] = useState(true);

    const loadProjects = async () => {
        setLoading(true);
        try {
            const list = await storageService.getAllProjects();
            setProjects(list);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadProjects();
    }, []);

    const handleDelete = async (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        if (confirm('Вы уверены, что хотите удалить этот проект?')) {
            await storageService.deleteProject(id);
            loadProjects();
        }
    };

    const handleExport = (e: React.MouseEvent, project: ProjectSnapshot) => {
        e.stopPropagation();
        const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `${project.name.replace(/\s+/g, '_')}.json`;
        a.click();
    };

    return (
        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[#1e1e1e] w-full max-w-4xl h-[80vh] rounded-2xl border border-slate-700 flex flex-col shadow-2xl overflow-hidden">
                <div className="p-6 border-b border-slate-700 flex justify-between items-center bg-[#252526]">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <FolderOpen className="text-blue-500" /> Библиотека Проектов
                    </h2>
                    <button onClick={onClose} className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm text-white transition">
                        Закрыть
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 no-scrollbar bg-[#111]">
                    {loading ? (
                        <div className="text-center text-slate-500 py-20">Загрузка...</div>
                    ) : projects.length === 0 ? (
                        <div className="text-center text-slate-500 py-20 flex flex-col items-center gap-4">
                            <FileBox size={48} className="opacity-20" />
                            <p>Нет сохраненных проектов</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {projects.map(p => (
                                <div 
                                    key={p.id}
                                    onClick={() => onLoad(p)}
                                    className="bg-[#252526] border border-slate-700 rounded-xl p-4 cursor-pointer hover:border-blue-500 hover:bg-[#2d2d2d] transition group relative overflow-hidden"
                                >
                                    <div className="flex justify-between items-start mb-2">
                                        <h3 className="font-bold text-white text-lg truncate pr-8">{p.name}</h3>
                                        <span className="text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-400 border border-slate-700">v{p.version}</span>
                                    </div>
                                    
                                    <div className="text-xs text-slate-500 mb-4 flex items-center gap-4">
                                        <span className="flex items-center gap-1"><Clock size={12}/> {new Date(p.timestamp).toLocaleDateString()}</span>
                                        <span className="flex items-center gap-1"><Layout size={12}/> {p.panels.length} дет.</span>
                                    </div>

                                    {/* Action Buttons */}
                                    <div className="flex gap-2 mt-4 pt-4 border-t border-slate-700/50">
                                        <button 
                                            onClick={(e) => handleExport(e, p)}
                                            className="p-2 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition"
                                            title="Скачать JSON"
                                        >
                                            <Download size={16}/>
                                        </button>
                                        <div className="flex-1"></div>
                                        <button 
                                            onClick={(e) => handleDelete(e, p.id)}
                                            className="p-2 rounded hover:bg-red-900/30 text-slate-600 hover:text-red-500 transition"
                                            title="Удалить"
                                        >
                                            <Trash2 size={16}/>
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ProjectLibrary;
