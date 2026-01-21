
import React, { useState, useEffect } from 'react';
import { useProjectStore } from '../store/projectStore';
import { generateCabinetConfig, analyzeProject, askExpert, ProjectAnalysisData } from '../services/geminiService';
import { aiServiceWithFallback } from '../services/aiServiceWithFallback';
import { checkCollisions } from '../services/CabinetGenerator';
import { Sparkles, Loader2, MessageSquare, ClipboardCheck, Wand2, ArrowRight, BookOpen, Zap, CheckCircle } from 'lucide-react';
import { Material, CabinetConfig, Section, Panel } from '../types';

interface AIAssistantProps {
    materialLibrary?: Material[];
    onApplyTemplate?: (template: { config: CabinetConfig, sections: Section[] }) => void;
    selectedPanel?: Panel | null;
}

interface PredictionResult {
  cabinetType?: string;
  complexity?: string;
  material?: string;
  suggestions?: string[];
  source?: 'local' | 'ollama' | 'hybrid';
}

const AIAssistant: React.FC<AIAssistantProps> = ({ materialLibrary = [], onApplyTemplate, selectedPanel }) => {
  const { panels } = useProjectStore();
  const [prompt, setPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [responseMessage, setResponseMessage] = useState<string | null>(null);
  const [generatedConfig, setGeneratedConfig] = useState<{ config: CabinetConfig, sections: Section[] } | null>(null);
  const [hasLocalModels, setHasLocalModels] = useState(false);
  const [predictions, setPredictions] = useState<PredictionResult | null>(null);
  const [predictionLoading, setPredictionLoading] = useState(false);

  useEffect(() => {
    const initializeAI = async () => {
      await aiServiceWithFallback.initialize();
      const available = await aiServiceWithFallback.isLocalServiceAvailable();
      setHasLocalModels(available);
    };
    initializeAI();
  }, []);

  useEffect(() => {
    if (!selectedPanel || !panels.length) {
      setPredictions(null);
      return;
    }

    const analyzePanelAutomatically = async () => {
      setPredictionLoading(true);
      try {
        const suggestions = await aiServiceWithFallback.getSuggestions(
          selectedPanel.width,
          selectedPanel.height,
          selectedPanel.depth,
          2,
          3
        );
        
        const complexity = await aiServiceWithFallback.analyzeComplexity(panels);
        
        setPredictions({
          cabinetType: selectedPanel.name,
          complexity,
          material: suggestions.material,
          suggestions: suggestions.suggestions,
          source: suggestions.source,
        });
      } catch (e) {
        console.error('Error analyzing panel:', e);
        setPredictions(null);
      } finally {
        setPredictionLoading(false);
      }
    };

    const debounceTimer = setTimeout(analyzePanelAutomatically, 500);
    return () => clearTimeout(debounceTimer);
  }, [selectedPanel, panels]);

  // --- Generation Logic ---
  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    
    setIsLoading(true);
    setResponseMessage(null);
    setGeneratedConfig(null);

    try {
      // 1. Attempt to generate a full parametric config first (Smarter)
      const configResult = await generateCabinetConfig(prompt, materialLibrary);
      
      if (configResult && configResult.config && configResult.sections) {
          setGeneratedConfig(configResult);
          setResponseMessage("Я подготовил параметрическую модель по вашему описанию. Проверьте параметры и нажмите 'Применить', чтобы открыть Мастер.");
      } else {
          setResponseMessage("Не удалось создать параметрическую модель. Попробуйте уточнить запрос (например: 'Шкаф 2000х2400 с 3 ящиками').");
      }
    } catch (e: any) {
      console.error(e);
      setResponseMessage(`Ошибка: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Expert Advice Logic ---
  const handleAskExpert = async () => {
      if (!prompt.trim()) return;
      setIsLoading(true);
      setResponseMessage(null);
      setGeneratedConfig(null);

      try {
          const answer = await askExpert(prompt);
          setResponseMessage(answer);
      } catch (e: any) {
          setResponseMessage(`Ошибка: ${e.message}`);
      } finally {
          setIsLoading(false);
      }
  };

  const handleApplyConfig = () => {
      if (generatedConfig && onApplyTemplate) {
          onApplyTemplate(generatedConfig);
      }
  };

  // --- Audit Logic ---
  const handleAnalyze = async () => {
    if (panels.length === 0) {
      setResponseMessage("Проект пуст. Нечего анализировать.");
      return;
    }
    setIsLoading(true);
    setResponseMessage("Сбор данных (Раскрой, Присадка, Конструктив)...");
    
    try {
      // 1. Calculate Stats
      const totalArea = panels.reduce((acc, p) => acc + (p.width * p.height) / 1000000, 0);
      
      const materialAreas = new Map<string, number>();
      panels.forEach(p => {
          const area = (p.width * p.height) / 1000000;
          const current = materialAreas.get(p.materialId) || 0;
          materialAreas.set(p.materialId, current + area);
      });

      const SHEET_AREA = 5.79; // 2800x2070 roughly
      let totalSheets = 0;
      const sheetBreakdown: string[] = [];

      materialAreas.forEach((area, matId) => {
          const sheets = Math.ceil((area * 1.25) / SHEET_AREA);
          totalSheets += sheets;
          sheetBreakdown.push(`${matId}: ${sheets} sheets (${area.toFixed(2)} m²)`);
      });

      const materials: string[] = Array.from(new Set(panels.map(p => p.materialId)));
      const uniqueParts = new Set(panels.map(p => `${p.width}x${p.height}x${p.materialId}`)).size;

      // 2. Aggregate Hardware
      const hardwareSummary: Record<string, number> = {};
      panels.forEach(p => {
          p.hardware.forEach(h => {
              const key = h.type; 
              hardwareSummary[key] = (hardwareSummary[key] || 0) + 1;
          });
      });

      // 3. Collision Check
      const collisions = checkCollisions(panels);

      // 4. Prepare Payload
      const analysisData: ProjectAnalysisData = {
          panels,
          stats: {
              totalArea,
              estimatedSheets: totalSheets,
              materialCount: materials.length,
              uniqueParts
          },
          hardwareSummary,
          materials,
          collisions
      };

      const report = await analyzeProject(analysisData);
      setResponseMessage(report);
    } catch (e: any) {
      setResponseMessage(`Ошибка анализа: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 p-4 border-r border-slate-200 w-full md:w-80 shadow-xl z-20">
      <div className="flex items-center gap-2 mb-1 text-indigo-700">
        <Sparkles className="w-5 h-5" />
        <h2 className="text-lg font-bold">ИИ Технолог</h2>
        {hasLocalModels && (
          <div className="ml-auto flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded text-[10px] font-bold">
            <CheckCircle size={12} /> Локальные модели
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto pr-1 space-y-4">
        {/* Real-time Predictions Panel */}
        {selectedPanel && (
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-3 rounded-lg shadow-sm border border-blue-200">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4 text-blue-600" />
              <h3 className="text-xs font-bold text-blue-900 uppercase">Анализ детали</h3>
              {predictionLoading && <Loader2 className="w-3 h-3 animate-spin ml-auto text-blue-600" />}
            </div>

            {predictions ? (
              <div className="space-y-2 text-xs">
                <div>
                  <span className="font-bold text-slate-700">Деталь:</span>
                  <span className="text-slate-600 ml-1">{predictions.cabinetType}</span>
                </div>

                {predictions.complexity && (
                  <div>
                    <span className="font-bold text-slate-700">Сложность:</span>
                    <span className="text-slate-600 ml-1 whitespace-normal">{predictions.complexity}</span>
                  </div>
                )}

                {predictions.material && (
                  <div>
                    <span className="font-bold text-slate-700">Материал:</span>
                    <span className="text-slate-600 ml-1">{predictions.material}</span>
                  </div>
                )}

                {predictions.source && (
                  <div className="text-[10px] text-slate-500 pt-1 border-t border-blue-200">
                    Источник: {predictions.source === 'local' ? '🔴 Локальная модель' : '☁️ Ollama'}
                  </div>
                )}
              </div>
            ) : predictionLoading ? (
              <div className="text-xs text-slate-600 flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin" /> Анализ...
              </div>
            ) : (
              <div className="text-xs text-slate-500">Выберите деталь для анализа</div>
            )}
          </div>
        )}

        {/* Chat / Gen Area */}
        <div className="bg-white p-3 rounded-lg shadow-sm border border-indigo-100">
            <label className="text-xs font-bold text-slate-700 mb-2 block">Ваш вопрос или описание:</label>
            <textarea
            className="w-full text-sm p-2 border border-slate-200 rounded focus:ring-2 focus:ring-indigo-500 focus:outline-none resize-none h-20 mb-2 bg-slate-50 text-slate-800"
            placeholder="Например: 'Шкаф 2м с ящиками' или 'Какая высота стола?'"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={isLoading}
            />
            <div className="flex gap-2">
                <button
                onClick={handleGenerate}
                disabled={isLoading || !prompt}
                className="flex-1 py-2 bg-indigo-600 text-white rounded text-xs font-bold hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-1 transition-colors shadow-md"
                >
                {isLoading ? <Loader2 className="animate-spin" size={14} /> : <><Wand2 size={14}/> Сгенерировать</>}
                </button>
                <button
                onClick={handleAskExpert}
                disabled={isLoading || !prompt}
                className="flex-1 py-2 bg-amber-600 text-white rounded text-xs font-bold hover:bg-amber-700 disabled:opacity-50 flex items-center justify-center gap-1 transition-colors shadow-md"
                >
                {isLoading ? <Loader2 className="animate-spin" size={14} /> : <><BookOpen size={14}/> Спросить совет</>}
                </button>
            </div>
        </div>

        {/* Response Area */}
        {responseMessage && (
            <div className="bg-white p-4 rounded-lg shadow-sm border border-slate-200 animate-in fade-in slide-in-from-bottom-2">
                <div className="flex items-center gap-2 mb-2 text-indigo-600 font-bold text-sm">
                    <MessageSquare size={16}/> Ответ ИИ:
                </div>
                <div className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {responseMessage}
                </div>
                {generatedConfig && (
                    <button 
                        onClick={handleApplyConfig}
                        className="mt-4 w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-bold text-sm flex items-center justify-center gap-2 transition shadow-md"
                    >
                        <ArrowRight size={16}/> Применить в Мастер
                    </button>
                )}
            </div>
        )}

        {/* Audit Button */}
        <div className="border-t border-slate-200 pt-4">
            <button 
                onClick={handleAnalyze}
                disabled={isLoading || panels.length === 0}
                className="w-full py-3 bg-slate-800 text-white rounded text-sm font-medium hover:bg-slate-700 disabled:opacity-50 flex items-center justify-center gap-2 transition shadow-lg"
            >
                {isLoading ? <Loader2 className="animate-spin" size={16} /> : <><ClipboardCheck size={16}/> Аудит проекта</>}
            </button>
            <p className="text-[10px] text-slate-500 mt-2 text-center">
                Проверка на ошибки, расчет материала и фурнитуры.
            </p>
        </div>
      </div>
    </div>
  );
};

export default AIAssistant;
