
import React from 'react';
import { useProjectStore } from '../store/projectStore';
import { Material } from '../types';
import PipelineStepper from './ProductionPipeline/PipelineStepper';
import DesignStage from './ProductionPipeline/DesignStage';
import CuttingStage from './ProductionPipeline/CuttingStage';
import EdgeStage from './ProductionPipeline/EdgeStage';
import DrillingStage from './ProductionPipeline/DrillingStage';
import AssemblyStage from './ProductionPipeline/AssemblyStage';
import Dashboard from './ProductionPipeline/Dashboard';
import RightSidebar from './ProductionPipeline/RightSidebar';
import { useProductionState } from '../hooks/useProductionState';
import { useProductionHandlers } from '../hooks/useProductionHandlers';

interface ProductionPipelineProps {
    materialLibrary: Material[];
}



const ProductionPipeline: React.FC<ProductionPipelineProps> = ({ materialLibrary }) => {
    const {
        panels,
        currentGlobalStage,
        setGlobalStage,
        setPanelStatus,
    } = useProjectStore();

    const { activeView, setActiveView, norms, scannerInput, setScannerInput } =
        useProductionState(panels);

    const { handleStageComplete, handleScan, generateCNC } = useProductionHandlers({
        panels,
        currentGlobalStage,
        materialLibrary,
        setGlobalStage,
        setPanelStatus,
        setScannerInput,
    });

    return (
        <div className="h-full flex flex-col bg-[#0f0f0f] text-slate-300">
            <div className="flex bg-[#1a1a1a] border-b border-slate-700">
                <button
                    onClick={() => setActiveView('pipeline')}
                    className={`px-6 py-4 text-sm font-bold uppercase tracking-wider border-b-2 transition ${
                        activeView === 'pipeline'
                            ? 'border-blue-500 text-blue-400 bg-slate-800'
                            : 'border-transparent text-slate-500 hover:text-slate-300'
                    }`}
                >
                    Производство
                </button>
                <button
                    onClick={() => setActiveView('dashboard')}
                    className={`px-6 py-4 text-sm font-bold uppercase tracking-wider border-b-2 transition ${
                        activeView === 'dashboard'
                            ? 'border-blue-500 text-blue-400 bg-slate-800'
                            : 'border-transparent text-slate-500 hover:text-slate-300'
                    }`}
                >
                    MES Дашборд
                </button>
            </div>

            {activeView === 'dashboard' ? (
                <Dashboard
                    panels={panels}
                    materialLibrary={materialLibrary}
                    currentGlobalStage={currentGlobalStage}
                />
            ) : (
                <>
                    <PipelineStepper currentStage={currentGlobalStage} onStageSelect={setGlobalStage} />

                    <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
                        <div className="flex-1 p-4 md:p-6 overflow-hidden order-1 md:order-1">
                            {currentGlobalStage === 'design' && (
                                <DesignStage panels={panels} onStageComplete={handleStageComplete} />
                            )}
                            {currentGlobalStage === 'cutting' && (
                                <CuttingStage
                                    panels={panels}
                                    materialLibrary={materialLibrary}
                                    onStageComplete={handleStageComplete}
                                />
                            )}
                            {currentGlobalStage === 'edging' && (
                                <EdgeStage
                                    panels={panels}
                                    onPanelStatusChange={setPanelStatus}
                                    onStageComplete={handleStageComplete}
                                />
                            )}
                            {currentGlobalStage === 'drilling' && (
                                <DrillingStage
                                    panels={panels}
                                    materialLibrary={materialLibrary}
                                    onGenerateCNC={generateCNC}
                                    onPanelStatusChange={setPanelStatus}
                                    onStageComplete={handleStageComplete}
                                />
                            )}
                            {currentGlobalStage === 'assembly' && (
                                <AssemblyStage onStageComplete={handleStageComplete} />
                            )}
                        </div>

                        <RightSidebar
                            panels={panels}
                            currentGlobalStage={currentGlobalStage}
                            norms={norms}
                            scannerInput={scannerInput}
                            onScannerInputChange={setScannerInput}
                            onScan={handleScan}
                        />
                    </div>
                </>
            )}
        </div>
    );
};

export default ProductionPipeline;
