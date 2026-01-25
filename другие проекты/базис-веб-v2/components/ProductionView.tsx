import React, { useState, useMemo, useEffect } from 'react';
import { useProjectStore } from '../store/projectStore';
import { Material, ProductionStatus, Panel, ProductionStage, ProductionNorms } from '../types';
import { 
    FileDown, Printer, Cog, ClipboardCheck, Factory, 
    Scan, Scissors, Layers, Hammer, PackageCheck, 
    CheckCircle2, ArrowRight, LayoutList, QrCode,
    Box, FileText, PlayCircle, CheckSquare, Clock
} from 'lucide-react';
import AssemblyDiagram from './AssemblyDiagram';

interface ProductionViewProps {
  materialLibrary: Material[];
}

// --- HELPERS ---

const calculateNorms = (panels: Panel[]): ProductionNorms => {
    const totalAreaM2 = panels.reduce((acc, p) => acc + (p.width * p.height) / 1000000, 0);
    const estimatedSheets = Math.ceil(totalAreaM2 / 5); 
    const cuttingTime = Math.max(20, estimatedSheets * 20);

    let totalEdges = 0;
    panels.forEach(p => {
        if (p.edging.top !== 'none') totalEdges++;
        if (p.edging.bottom !== 'none') totalEdges++;
        if (p.edging.left !== 'none') totalEdges++;
        if (p.edging.right !== 'none') totalEdges++;
    });
    const edgingTime = Math.ceil(totalEdges * 0.5);

    const panelsWithHw = panels.filter(p => p.hardware && p.hardware.length > 0).length;
    const drillingTime = Math.ceil(panelsWithHw * 2);

    let assemblyTime = 30;
    panels.forEach(p => {
        if (p.openingType === 'drawer') assemblyTime += 15;
        if (p.openingType !== 'none' && p.openingType !== 'drawer') assemblyTime += 10;
        if (p.layer === 'shelves') assemblyTime += 5;
    });

    return {
        cuttingTime,
        edgingTime,
        drillingTime,
        assemblyTime,
        totalTimeMinutes: cuttingTime + edgingTime + drillingTime + assemblyTime
    };
};

const QRCodeSVG: React.FC<{ value: string, size?: number }> = ({ value, size = 64 }) => {
    const seed = value.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    const cells: React.ReactNode[] = [];
    const gridSize = 8;
    const cellSize = size / gridSize;
    
    // Markers
    const marker = (cx: number, cy: number) => (
        <g>
            <rect x={cx} y={cy} width={cellSize*3} height={cellSize*3} fill="black"/>
            <rect x={cx+cellSize*0.5} y={cy+cellSize*0.5} width={cellSize*2} height={cellSize*2} fill="white"/>
            <rect x={cx+cellSize} y={cy+cellSize} width={cellSize} height={cellSize} fill="black"/>
        </g>
    );

    for(let y=0; y<gridSize; y++) {
        for(let x=0; x<gridSize; x++) {
            if ((x<3 && y<3) || (x>4 && y<3) || (x<3 && y>4)) continue;
            const isFilled = Math.sin(seed * (x+1) * (y+1)) > 0;
            if (isFilled) cells.push(<rect key={`${x}-${y}`} x={x*cellSize} y={y*cellSize} width={cellSize} height={cellSize} fill="black"/>);
        }
    }

    return (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
            <rect width={size} height={size} fill="white"/>
            {marker(0,0)}
            {marker(size - cellSize*3, 0)}
            {marker(0, size - cellSize*3)}
            {cells}
        </svg>
    );
};

const ProductionLabel: React.FC<{ panel: Panel, material?: Material, orderId: string, index: number }> = ({ panel, material, orderId, index }) => {
    return (
        <div className="bg-white text-black p-2 border border-slate-300 w-[300px] h-[180px] flex flex-col justify-between shadow-sm break-inside-avoid relative overflow-hidden print:border-black">
            <div className="flex justify-between items-start border-b border-black pb-1 mb-1">
                <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider">Заказ №{orderId}</div>
                    <div className="text-lg font-bold leading-none mt-1">{panel.name.substring(0, 18)}</div>
                </div>
                <div className="text-2xl font-bold font-mono">#{index + 1}</div>
            </div>
            
            <div className="flex gap-2 h-full">
                <div className="flex-1 flex flex-col justify-between">
                    <div className="text-xs font-mono">
                        <div className="flex justify-between"><span>L:</span> <b>{panel.width}</b></div>
                        <div className="flex justify-between"><span>W:</span> <b>{panel.height}</b></div>
                        <div className="mt-1 text-[10px] text-slate-600 leading-tight">{material?.name}</div>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-0.5 text-[8px] border border-black mt-2 text-center">
                        <div className="bg-slate-200 p-0.5">КРОМКА</div>
                        <div className="col-span-2 grid grid-cols-2">
                            <div className="border-r border-b border-black/20">{panel.edging.top !== 'none' ? 'TOP' : '-'}</div>
                            <div className="border-b border-black/20">{panel.edging.right !== 'none' ? 'RGT' : '-'}</div>
                            <div className="border-r border-black/20">{panel.edging.bottom !== 'none' ? 'BTM' : '-'}</div>
                            <div>{panel.edging.left !== 'none' ? 'LFT' : '-'}</div>
                        </div>
                    </div>
                </div>
                
                <div className="flex flex-col items-center justify-center border-l border-slate-200 pl-2">
                    <QRCodeSVG value={panel.id} size={80} />
                    <div className="text-[8px] font-mono mt-1">{panel.id.slice(-8)}</div>
                </div>
            </div>
            
            <div className="mt-1 flex gap-1">
                {(panel.hardware && panel.hardware.length > 0) && <span className="bg-black text-white text-[9px] px-1 rounded">ПРИСАДКА</span>}
                {(panel.groove?.enabled) && <span className="bg-black text-white text-[9px] px-1 rounded">ПАЗ</span>}
                {panel.currentStage === 'shipping' && <span className="bg-green-600 text-white text-[9px] px-1 rounded">ГОТОВО</span>}
            </div>
        </div>
    );
};

// --- SUB-COMPONENTS ---

const PipelineStepper: React.FC<{ currentStage: ProductionStage, onStageSelect: (s: ProductionStage) => void }> = ({ currentStage, onStageSelect }) => {
    const stages: { id: ProductionStage, label: string, icon: React.ElementType }[] = [
        { id: 'design', label: 'Проект', icon: Box },
        { id: 'cutting', label: 'Раскрой', icon: Scissors },
        { id: 'edging', label: 'Кромление', icon: Layers },
        { id: 'drilling', label: 'Присадка', icon: Factory },
        { id: 'assembly', label: 'Сборка', icon: Hammer },
    ];

    const currentIndex = stages.findIndex(s => s.id === currentStage);

    return (
        <div className="flex items-center justify-start md:justify-between px-4 md:px-8 py-4 bg-[#1a1a1a] border-b border-slate-700 overflow-x-auto print:hidden gap-4 no-scrollbar">
            {stages.map((stage, idx) => {
                const isActive = stage.id === currentStage;
                const isCompleted = idx < currentIndex;
                
                return (
                    <div key={stage.id} 
                         className={`flex flex-col items-center gap-2 cursor-pointer transition group min-w-[70px] md:min-w-[80px] shrink-0 ${isActive ? 'opacity-100' : 'opacity-50 hover:opacity-80'}`}
                         onClick={() => onStageSelect(stage.id)}
                    >
                        <div className={`w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center border-2 transition z-10 relative
                            ${isActive ? 'bg-blue-600 border-blue-400 text-white shadow-[0_0_15px_rgba(37,99,235,0.5)]' : ''}
                            ${isCompleted ? 'bg-emerald-900 border-emerald-600 text-emerald-400' : ''}
                            ${!isActive && !isCompleted ? 'bg-slate-800 border-slate-600 text-slate-400' : ''}
                        `}>
                            {isCompleted ? <CheckCircle2 size={16} className="md:w-5 md:h-5"/> : <stage.icon size={16} className="md:w-[18px] md:h-[18px]"/>}
                        </div>
                        <span className={`text-[10px] md:text-xs font-bold uppercase tracking-wider ${isActive ? 'text-blue-400' : 'text-slate-500'}`}>
                            {stage.label}
                        </span>
                    </div>
                );
            })}
        </div>
    );
};

const ProductionPipeline: React.FC<ProductionViewProps> = ({ materialLibrary }) => {
    const { 
        panels, 
        currentGlobalStage, 
        setGlobalStage, 
        setPanelStatus
    } = useProjectStore();

    const [norms, setNorms] = useState<ProductionNorms>({ totalTimeMinutes:0, cuttingTime:0, edgingTime:0, drillingTime:0, assemblyTime:0 });
    const [scannerInput, setScannerInput] = useState('');
    const [viewLabels, setViewLabels] = useState(false);

    useEffect(() => {
        setNorms(calculateNorms(panels));
    }, [panels]);

    // Derived Stats for Current Stage
    const stageStats = useMemo(() => {
        const completed = panels.filter(p => p.productionStatus === 'completed').length;
        const total = panels.length;
        const progress = total > 0 ? Math.round((completed / total) * 100) : 0;
        return { completed, total, progress };
    }, [panels, currentGlobalStage]);

    // --- HANDLERS ---

    const handleStageComplete = () => {
        const stages: ProductionStage[] = ['design', 'cutting', 'edging', 'drilling', 'assembly'];
        const idx = stages.indexOf(currentGlobalStage);
        if (idx < stages.length - 1) {
            setGlobalStage(stages[idx + 1]);
            panels.forEach(p => setPanelStatus(p.id, 'pending')); 
        } else {
            alert("Заказ полностью выполнен!");
        }
    };

    const handleScan = (e: React.FormEvent) => {
        e.preventDefault();
        const found = panels.find(p => p.id.includes(scannerInput) || p.name.toLowerCase().includes(scannerInput.toLowerCase()));
        if (found) {
            setPanelStatus(found.id, 'completed');
            setScannerInput('');
        } else {
            alert("Деталь не найдена");
        }
    };

    const generateCNC = () => {
        let csv = "DetalID;Name;L;W;TH;Material;Qty;OpType;X;Y;Z;Diam;Depth\n";
        panels.forEach((p, idx) => {
            const mat = materialLibrary.find(m => m.id === p.materialId);
            const baseLine = `${idx+1};${p.name};${p.width};${p.height};${p.depth};${mat?.name || 'Unknown'};1`;
            p.hardware.forEach(h => {
                let depth = h.depth || 13;
                if (h.type === 'dowel') depth = 30; 
                csv += `${baseLine};DRILL;${h.x};${h.y};0;${h.diameter || 5};${depth}\n`;
            });
            if (p.groove && p.groove.enabled) {
                 csv += `${baseLine};GROOVE;${p.groove.offset};0;0;${p.groove.width};${p.groove.depth}\n`;
            }
        });
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.setAttribute("download", "production_cnc.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // --- RENDER CONTENT BY STAGE ---

    const renderDesignStage = () => (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 h-full">
            <div className="bg-[#222] p-8 rounded-xl border border-slate-700 flex flex-col justify-center items-center text-center">
                <Box size={64} className="text-blue-500 mb-4"/>
                <h2 className="text-2xl font-bold text-white mb-2">Проектирование завершено</h2>
                <p className="text-slate-400 mb-6">3D модель построена, деталировка сформирована. <br/>Готово к передаче в производство.</p>
                <div className="grid grid-cols-2 gap-4 w-full max-w-md text-left bg-[#1a1a1a] p-4 rounded-lg border border-slate-800">
                    <div>
                        <div className="text-xs text-slate-500">Всего деталей</div>
                        <div className="text-xl font-mono text-white">{panels.length} шт</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">Материалы</div>
                        <div className="text-xl font-mono text-white">{new Set(panels.map(p => p.materialId)).size} типа</div>
                    </div>
                </div>
            </div>
            <div className="space-y-4">
                 <div className="bg-[#222] p-6 rounded-xl border border-slate-700">
                     <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2"><FileText size={20}/> Документация</h3>
                     <button className="w-full py-3 bg-[#333] hover:bg-[#444] rounded flex items-center justify-between px-4 mb-2 transition">
                         <span>Коммерческое предложение</span> <ArrowRight size={16}/>
                     </button>
                     <button className="w-full py-3 bg-[#333] hover:bg-[#444] rounded flex items-center justify-between px-4 mb-2 transition">
                         <span>Спецификация материалов</span> <ArrowRight size={16}/>
                     </button>
                     <button onClick={handleStageComplete} className="w-full py-4 mt-6 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded flex items-center justify-center gap-2 shadow-lg shadow-blue-900/20">
                         <PlayCircle size={20}/> Передать в раскрой
                     </button>
                 </div>
            </div>
        </div>
    );

    const renderCuttingStage = () => (
        <div className="h-full flex flex-col">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                     <h2 className="text-xl font-bold text-white flex items-center gap-2"><Scissors className="text-orange-500"/> Карта Раскроя</h2>
                     <p className="text-slate-400 text-sm">Оптимизация листа и печать этикеток</p>
                </div>
                <div className="flex gap-2 w-full md:w-auto">
                    <button onClick={() => setViewLabels(!viewLabels)} className={`flex-1 md:flex-none px-4 py-2 font-bold rounded flex items-center justify-center gap-2 ${viewLabels ? 'bg-white text-black' : 'bg-slate-700 text-white'}`}>
                        <Printer size={16}/> <span className="hidden sm:inline">{viewLabels ? 'Закрыть Этикетки' : 'Печать Этикеток'}</span><span className="sm:hidden">Этикетки</span>
                    </button>
                    <button onClick={handleStageComplete} className="flex-1 md:flex-none px-4 py-2 bg-emerald-600 text-white font-bold rounded flex items-center justify-center gap-2 hover:bg-emerald-700">
                        <CheckCircle2 size={16}/> <span className="hidden sm:inline">Раскрой Завершен</span><span className="sm:hidden">Готово</span>
                    </button>
                </div>
            </div>

            {viewLabels ? (
                <div className="flex-1 overflow-auto bg-slate-300 p-8 rounded-xl shadow-inner no-scrollbar">
                    <div className="flex justify-end mb-4 print:hidden"><button onClick={() => window.print()} className="bg-blue-600 text-white px-4 py-2 rounded font-bold">Печать (Ctrl+P)</button></div>
                    <div className="flex flex-wrap gap-4 justify-center print:block">
                        {panels.map((p, i) => (
                            <ProductionLabel key={p.id} panel={p} material={materialLibrary.find(m => m.id === p.materialId)} orderId="1024" index={i} />
                        ))}
                    </div>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 overflow-y-auto pb-20 no-scrollbar">
                    {panels.map((p, i) => (
                        <div key={p.id} className="bg-white text-black p-3 rounded shadow-lg relative break-inside-avoid">
                            <div className="flex justify-between items-start border-b border-black/20 pb-2 mb-2">
                                <div>
                                    <div className="text-[10px] uppercase font-bold text-slate-500">Det #{i+1}</div>
                                    <div className="font-bold text-lg leading-tight">{p.name}</div>
                                </div>
                                <QRCodeSVG value={p.id} size={48}/>
                            </div>
                            <div className="flex justify-between text-xs font-mono font-bold">
                                <span>{p.width} x {p.height}</span>
                                <span>{materialLibrary.find(m => m.id === p.materialId)?.name.substring(0,10)}...</span>
                            </div>
                            <div className="mt-2 flex gap-1">
                                {(p.edging.top !== 'none' || p.edging.bottom !== 'none' || p.edging.left !== 'none' || p.edging.right !== 'none') && 
                                    <span className="px-1 bg-black text-white text-[9px] rounded">EDGE</span>}
                                {p.hardware.length > 0 && <span className="px-1 bg-black text-white text-[9px] rounded">DRILL</span>}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );

    const renderEdgingStage = () => (
        <div className="h-full flex flex-col">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                     <h2 className="text-xl font-bold text-white flex items-center gap-2"><Layers className="text-blue-500"/> Участок Кромления</h2>
                     <p className="text-slate-400 text-sm">Нанесение кромки согласно карте</p>
                </div>
                <div className="flex gap-4 items-center w-full md:w-auto justify-between md:justify-end">
                    <div className="hidden sm:flex items-center gap-2 bg-[#222] px-3 py-1 rounded border border-slate-700">
                        <div className="w-3 h-3 bg-red-500 rounded-full"></div> <span className="text-xs text-slate-300">2.0 мм</span>
                        <div className="w-3 h-3 bg-blue-500 rounded-full ml-2"></div> <span className="text-xs text-slate-300">0.4 мм</span>
                    </div>
                    <button onClick={handleStageComplete} className="px-4 py-2 bg-emerald-600 text-white font-bold rounded flex items-center gap-2 hover:bg-emerald-700">
                        <CheckCircle2 size={16}/> <span className="hidden sm:inline">Кромление Завершено</span><span className="sm:hidden">Готово</span>
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 no-scrollbar">
                 {panels.map((p, i) => (
                     <div key={p.id} className="bg-[#222] p-4 rounded border border-slate-700 flex justify-between items-center group">
                         <div className="flex items-center gap-4">
                             <div className="w-8 h-8 bg-slate-800 rounded flex items-center justify-center font-bold font-mono text-slate-400">{i+1}</div>
                             <div>
                                 <div className="font-bold text-white">{p.name}</div>
                                 <div className="text-xs text-slate-500 font-mono">{p.width} x {p.height}</div>
                             </div>
                         </div>
                         
                         {/* Edging Visual Map */}
                         <div className="relative w-20 h-12 md:w-32 md:h-20 bg-slate-800 border border-slate-600 shrink-0">
                             {p.edging.top !== 'none' && <div className={`absolute top-0 left-0 right-0 h-1 ${p.edging.top==='2.0'?'bg-red-500':'bg-blue-500'}`}/>}
                             {p.edging.bottom !== 'none' && <div className={`absolute bottom-0 left-0 right-0 h-1 ${p.edging.bottom==='2.0'?'bg-red-500':'bg-blue-500'}`}/>}
                             {p.edging.left !== 'none' && <div className={`absolute top-0 bottom-0 left-0 w-1 ${p.edging.left==='2.0'?'bg-red-500':'bg-blue-500'}`}/>}
                             {p.edging.right !== 'none' && <div className={`absolute top-0 bottom-0 right-0 w-1 ${p.edging.right==='2.0'?'bg-red-500':'bg-blue-500'}`}/>}
                             <div className="absolute inset-0 flex items-center justify-center text-[8px] md:text-[10px] text-slate-600">СХЕМА</div>
                         </div>

                         <div className="flex items-center gap-4">
                            <button 
                                onClick={() => setPanelStatus(p.id, p.productionStatus === 'completed' ? 'pending' : 'completed')}
                                className={`w-10 h-10 rounded flex items-center justify-center transition ${p.productionStatus === 'completed' ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-500 hover:bg-slate-600'}`}
                            >
                                <CheckCircle2 size={20}/>
                            </button>
                         </div>
                     </div>
                 ))}
            </div>
        </div>
    );

    const renderDrillingStage = () => (
        <div className="h-full flex flex-col">
             <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                     <h2 className="text-xl font-bold text-white flex items-center gap-2"><Factory className="text-purple-500"/> Участок Присадки (ЧПУ)</h2>
                     <p className="text-slate-400 text-sm">Сверление отверстий</p>
                </div>
                <div className="flex gap-2 w-full md:w-auto">
                    <button onClick={generateCNC} className="flex-1 md:flex-none px-4 py-2 bg-purple-600 text-white font-bold rounded flex items-center justify-center gap-2 hover:bg-purple-700">
                        <FileDown size={16}/> <span className="hidden sm:inline">CSV для ЧПУ</span><span className="sm:hidden">CSV</span>
                    </button>
                    <button onClick={handleStageComplete} className="flex-1 md:flex-none px-4 py-2 bg-emerald-600 text-white font-bold rounded flex items-center justify-center gap-2 hover:bg-emerald-700">
                        <CheckCircle2 size={16}/> <span className="hidden sm:inline">Присадка Завершена</span><span className="sm:hidden">Готово</span>
                    </button>
                </div>
            </div>
            
            <div className="flex-1 overflow-y-auto no-scrollbar">
                {/* Desktop Table */}
                <table className="w-full text-left text-sm text-slate-300 hidden md:table">
                    <thead className="bg-[#222] text-xs uppercase text-slate-500 font-bold sticky top-0">
                        <tr>
                            <th className="p-3">ID</th>
                            <th className="p-3">Деталь</th>
                            <th className="p-3">Отверстия</th>
                            <th className="p-3">Типы</th>
                            <th className="p-3 text-center">Статус</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                        {panels.filter(p => p.hardware.length > 0 || p.groove?.enabled).map((p, i) => (
                            <tr key={p.id} className="hover:bg-slate-800/50">
                                <td className="p-3 font-mono text-slate-500">#{i+1}</td>
                                <td className="p-3 font-bold">{p.name}</td>
                                <td className="p-3 font-mono">{p.hardware.length} шт</td>
                                <td className="p-3">
                                    <div className="flex gap-1 flex-wrap">
                                        {Array.from(new Set(p.hardware.map(h => h.type))).map((t: string) => (
                                            <span key={t} className="px-1.5 py-0.5 bg-slate-700 rounded text-[10px] text-slate-300 uppercase">{t}</span>
                                        ))}
                                        {p.groove?.enabled && <span className="px-1.5 py-0.5 bg-blue-900/50 text-blue-300 rounded text-[10px] uppercase">ПАЗ</span>}
                                    </div>
                                </td>
                                <td className="p-3 text-center">
                                    <button 
                                        onClick={() => setPanelStatus(p.id, p.productionStatus === 'completed' ? 'pending' : 'completed')}
                                        className={`px-3 py-1 rounded text-xs font-bold ${p.productionStatus === 'completed' ? 'bg-emerald-900/50 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400 border border-slate-700'}`}
                                    >
                                        {p.productionStatus === 'completed' ? 'ГОТОВО' : 'ОЖИДАНИЕ'}
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>

                {/* Mobile Cards */}
                <div className="md:hidden space-y-3">
                    {panels.filter(p => p.hardware.length > 0 || p.groove?.enabled).map((p, i) => (
                        <div key={p.id} className="bg-[#222] p-3 rounded border border-slate-700 flex flex-col gap-2">
                            <div className="flex justify-between items-center">
                                <span className="text-xs text-slate-500 font-mono">#{i+1}</span>
                                <button 
                                    onClick={() => setPanelStatus(p.id, p.productionStatus === 'completed' ? 'pending' : 'completed')}
                                    className={`px-3 py-1 rounded text-[10px] font-bold ${p.productionStatus === 'completed' ? 'bg-emerald-900/50 text-emerald-400' : 'bg-slate-800 text-slate-400'}`}
                                >
                                    {p.productionStatus === 'completed' ? 'ГОТОВО' : 'В РАБОТЕ'}
                                </button>
                            </div>
                            <div className="font-bold text-white text-sm">{p.name}</div>
                            <div className="flex gap-2 text-xs text-slate-400">
                                <span>{p.hardware.length} отверстий</span>
                                {p.groove?.enabled && <span className="text-blue-400">+ ПАЗ</span>}
                            </div>
                            <div className="flex flex-wrap gap-1">
                                {Array.from(new Set(p.hardware.map(h => h.type))).map((t: string) => (
                                    <span key={t} className="px-1.5 py-0.5 bg-slate-800 rounded text-[9px] text-slate-500 uppercase">{t}</span>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );

    const renderAssemblyStage = () => (
         <div className="h-full flex flex-col">
             <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-2">
                <div>
                     <h2 className="text-xl font-bold text-white flex items-center gap-2"><Hammer className="text-emerald-500"/> Цех Сборки</h2>
                     <p className="text-slate-400 text-sm">Финальная сборка и упаковка</p>
                </div>
                <button onClick={handleStageComplete} className="w-full md:w-auto px-4 py-2 bg-emerald-600 text-white font-bold rounded flex items-center justify-center gap-2 hover:bg-emerald-700 shadow-[0_0_20px_rgba(5,150,105,0.4)]">
                        <PackageCheck size={16}/> <span className="hidden sm:inline">Заказ Готов к Отгрузке</span><span className="sm:hidden">Готово</span>
                </button>
            </div>
            
            <div className="flex-1 bg-white rounded-xl overflow-hidden shadow-2xl relative border border-slate-600 flex flex-col">
                <div className="flex-1 relative">
                    <AssemblyDiagram />
                </div>
                
                {/* Overlay Assembly Checklist - Responsive Position */}
                <div className="relative md:absolute md:top-4 md:right-4 w-full md:w-64 bg-slate-900/90 backdrop-blur border-t md:border border-slate-700 rounded-none md:rounded-lg p-4 text-slate-300">
                    <h4 className="font-bold text-white mb-3 text-sm flex items-center gap-2"><CheckSquare size={14}/> Чек-лист сборщика</h4>
                    <div className="grid grid-cols-2 md:grid-cols-1 gap-2 text-xs">
                        <label className="flex items-center gap-2 cursor-pointer hover:text-white">
                            <input type="checkbox" className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0"/>
                            Сборка корпуса
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer hover:text-white">
                            <input type="checkbox" className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0"/>
                            Проверка диагоналей
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer hover:text-white">
                            <input type="checkbox" className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0"/>
                            Задняя стенка
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer hover:text-white">
                            <input type="checkbox" className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0"/>
                            Ящики/фасады
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer hover:text-white">
                            <input type="checkbox" className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0"/>
                            Регулировка
                        </label>
                    </div>
                </div>
            </div>
         </div>
    );

    return (
        <div className="h-full flex flex-col bg-[#0f0f0f] text-slate-300">
            <PipelineStepper currentStage={currentGlobalStage} onStageSelect={setGlobalStage} />

            <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
                <div className="flex-1 p-4 md:p-6 overflow-hidden order-1 md:order-1 no-scrollbar">
                    {currentGlobalStage === 'design' && renderDesignStage()}
                    {currentGlobalStage === 'cutting' && renderCuttingStage()}
                    {currentGlobalStage === 'edging' && renderEdgingStage()}
                    {currentGlobalStage === 'drilling' && renderDrillingStage()}
                    {currentGlobalStage === 'assembly' && renderAssemblyStage()}
                </div>

                {/* RIGHT SIDEBAR (STATS) - Collapsible on Mobile */}
                <div className="w-full md:w-80 bg-[#1a1a1a] border-t md:border-t-0 md:border-l border-slate-700 flex flex-col overflow-y-auto print:hidden order-2 md:order-2 shrink-0 max-h-[300px] md:max-h-none no-scrollbar">
                    <div className="p-4 border-b border-slate-700 flex justify-between md:block items-center">
                        <div>
                            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Статус Заказа</div>
                            <div className="text-lg font-bold text-white mb-1">Заказ #2026-001</div>
                            <div className="flex items-center gap-2 text-sm">
                                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                                <span className="text-emerald-400 capitalize">{currentGlobalStage}</span>
                            </div>
                        </div>
                        {/* Mobile Toggle for details could go here, but let's just show progress on mobile */}
                        <div className="md:hidden text-right">
                             <div className="text-2xl font-bold text-blue-500">{stageStats.progress}%</div>
                             <div className="text-xs text-slate-500">Завершено</div>
                        </div>
                    </div>

                    <div className="p-4 border-b border-slate-700 hidden md:block">
                         <div className="flex justify-between items-center mb-2">
                             <span className="text-xs font-bold text-slate-500 uppercase">Прогресс этапа</span>
                             <span className="text-xs font-mono text-blue-400">{stageStats.progress}%</span>
                         </div>
                         <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                             <div className="h-full bg-blue-600 transition-all duration-500" style={{ width: `${stageStats.progress}%` }}></div>
                         </div>
                         <div className="text-xs text-slate-500 mt-2 text-right">{stageStats.completed} из {stageStats.total} деталей</div>
                    </div>

                    <div className="hidden md:block p-4 border-b border-slate-700">
                        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Время (План)</div>
                        <div className="space-y-3">
                            <div className="flex justify-between text-sm">
                                <span className="flex items-center gap-2"><Scissors size={14}/> Раскрой</span>
                                <span className="font-mono text-slate-300">{norms.cuttingTime} м</span>
                            </div>
                            <div className="flex justify-between text-sm">
                                <span className="flex items-center gap-2"><Layers size={14}/> Кромка</span>
                                <span className="font-mono text-slate-300">{norms.edgingTime} м</span>
                            </div>
                            <div className="flex justify-between text-sm">
                                <span className="flex items-center gap-2"><Factory size={14}/> Присадка</span>
                                <span className="font-mono text-slate-300">{norms.drillingTime} м</span>
                            </div>
                            <div className="flex justify-between text-sm">
                                <span className="flex items-center gap-2"><Hammer size={14}/> Сборка</span>
                                <span className="font-mono text-slate-300">{norms.assemblyTime} м</span>
                            </div>
                            <div className="pt-2 border-t border-slate-800 flex justify-between text-sm font-bold text-white">
                                <span>ИТОГО:</span>
                                <span className="flex items-center gap-1"><Clock size={14} className="text-orange-500"/> {Math.ceil(norms.totalTimeMinutes/60)}ч {norms.totalTimeMinutes%60}м</span>
                            </div>
                        </div>
                    </div>

                    <div className="p-4 mt-auto">
                        <div className="bg-[#111] border border-slate-700 p-4 rounded-xl">
                            <div className="text-xs font-bold text-slate-500 uppercase mb-2 flex items-center gap-2"><Scan size={14}/> Сканер QR</div>
                            <form onSubmit={handleScan}>
                                <input 
                                    type="text" 
                                    value={scannerInput}
                                    onChange={(e) => setScannerInput(e.target.value)}
                                    placeholder="Сканировать ID..." 
                                    className="w-full bg-[#222] border border-slate-600 rounded p-2 text-sm text-white focus:border-blue-500 focus:outline-none"
                                />
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ProductionPipeline;