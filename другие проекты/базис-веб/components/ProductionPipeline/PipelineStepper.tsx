import React from 'react';
import {
  CheckCircle2,
  Box,
  Scissors,
  Layers,
  Factory,
  Hammer,
} from 'lucide-react';
import { ProductionStage } from '../../types';

interface PipelineStepperProps {
  currentStage: ProductionStage;
  onStageSelect: (s: ProductionStage) => void;
}

const PipelineStepper: React.FC<PipelineStepperProps> = ({
  currentStage,
  onStageSelect,
}) => {
  const stages: { id: ProductionStage; label: string; icon: React.ElementType }[] = [
    { id: 'design', label: 'Проект', icon: Box },
    { id: 'cutting', label: 'Раскрой', icon: Scissors },
    { id: 'edging', label: 'Кромление', icon: Layers },
    { id: 'drilling', label: 'Присадка', icon: Factory },
    { id: 'assembly', label: 'Сборка', icon: Hammer },
  ];

  const currentIndex = stages.findIndex((s) => s.id === currentStage);

  return (
    <div className="flex items-center justify-start md:justify-between px-4 md:px-8 py-4 bg-[#1a1a1a] border-b border-slate-700 overflow-x-auto print:hidden gap-4 no-scrollbar">
      {stages.map((stage, idx) => {
        const isActive = stage.id === currentStage;
        const isCompleted = idx < currentIndex;

        return (
          <div
            key={stage.id}
            className={`flex flex-col items-center gap-2 cursor-pointer transition group min-w-[70px] md:min-w-[80px] shrink-0 ${
              isActive ? 'opacity-100' : 'opacity-50 hover:opacity-80'
            }`}
            onClick={() => onStageSelect(stage.id)}
          >
            <div
              className={`w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center border-2 transition z-10 relative
                ${
                  isActive
                    ? 'bg-blue-600 border-blue-400 text-white shadow-[0_0_15px_rgba(37,99,235,0.5)]'
                    : ''
                }
                ${isCompleted ? 'bg-emerald-900 border-emerald-600 text-emerald-400' : ''}
                ${
                  !isActive && !isCompleted
                    ? 'bg-slate-800 border-slate-600 text-slate-400'
                    : ''
                }
              `}
            >
              {isCompleted ? (
                <CheckCircle2 size={16} className="md:w-5 md:h-5" />
              ) : (
                <stage.icon size={16} className="md:w-[18px] md:h-[18px]" />
              )}
            </div>
            <span
              className={`text-[10px] md:text-xs font-bold uppercase tracking-wider ${
                isActive ? 'text-blue-400' : 'text-slate-500'
              }`}
            >
              {stage.label}
            </span>
          </div>
        );
      })}
    </div>
  );
};

export default PipelineStepper;
