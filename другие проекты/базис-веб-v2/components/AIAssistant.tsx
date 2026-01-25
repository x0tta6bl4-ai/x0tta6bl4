
import React, { useState, useRef } from 'react';
import { useProjectStore } from '../store/projectStore';
import { generateCabinetConfig, analyzeProject, askExpert, analyzeImage, ProjectAnalysisData } from '../services/geminiService';
import { checkCollisions } from '../services/CabinetGenerator';
import { Sparkles, Loader2, MessageSquare, ClipboardCheck, Wand2, ArrowRight, BookOpen, ImagePlus, X, Trash2, Camera } from 'lucide-react';
import { Material, CabinetConfig, Section } from '../types';

interface AIAssistantProps {
    materialLibrary?: Material[];
    onApplyTemplate?: (template: { config: CabinetConfig, sections: Section[] }) => void;
}

const AIAssistant: React.FC<AIAssistantProps> = ({ materialLibrary = [], onApplyTemplate }) => {
  const { panels } = useProjectStore();
  const [prompt, setPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [responseMessage, setResponseMessage] = useState<string | null>(null);
  const [generatedConfig, setGeneratedConfig] = useState<{ config: CabinetConfig, sections: Section[] } | null>(null);
  
  // Image State
  const [selectedImage, setSelectedImage] = useState<{data: string, mimeType: string, preview: string} | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      if (!file.type.startsWith('image/')) {
          setResponseMessage("Пожалуйста, выберите изображение.");
          return;
      }

      const reader = new FileReader();
      reader.onloadend = () => {
          const result = reader.result as string;
          // result is data:image/jpeg;base64,....
          const base64Data = result.split(',')[1];
          const mimeType = result.split(',')[0].split(':')[1].split(';')[0];
          setSelectedImage({
              data: base64Data,
              mimeType: mimeType,
              preview: result
          });
          // Reset file inputs to allow re-selecting same file
          if (fileInputRef.current) fileInputRef.current.value = '';
          if (cameraInputRef.current) cameraInputRef.current.value = '';
      };
      reader.readAsDataURL(file);
  };

  const clearImage = () => {
      setSelectedImage(null);
  };

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
      if (!prompt.trim() && !selectedImage) return;
      setIsLoading(true);
      setResponseMessage(null);
      setGeneratedConfig(null);

      try {
          let answer;
          if (selectedImage) {
              answer = await analyzeImage(prompt, selectedImage.data, selectedImage.mimeType);
          } else {
              answer = await askExpert(prompt);
          }
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
      <div className="flex items-center gap-2 mb-4 text-indigo-700">
        <Sparkles className="w-5 h-5" />
        <h2 className="text-lg font-bold">ИИ Технолог</h2>
      </div>

      <div className="flex-1 overflow-y-auto pr-1 space-y-4 no-scrollbar">
        {/* Chat / Gen Area */}
        <div className="bg-white p-3 rounded-lg shadow-sm border border-indigo-100">
            <label className="text-xs font-bold text-slate-700 mb-2 block">Ваш вопрос или описание:</label>
            
            {/* Image Preview */}
            {selectedImage && (
                <div className="relative mb-2 rounded-lg overflow-hidden border border-slate-200 group">
                    <img src={selectedImage.preview} alt="Selected" className="w-full h-32 object-cover" />
                    <button 
                        onClick={clearImage}
                        className="absolute top-1 right-1 p-1 bg-black/50 text-white rounded-full hover:bg-red-600 transition"
                    >
                        <X size={14} />
                    </button>
                    <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-[10px] p-1 text-center font-bold">
                        ИЗОБРАЖЕНИЕ ВЫБРАНО
                    </div>
                </div>
            )}

            <div className="relative">
                <textarea
                    className="w-full text-sm p-2 border border-slate-200 rounded focus:ring-2 focus:ring-indigo-500 focus:outline-none resize-none h-20 mb-2 bg-slate-50 text-slate-800 pr-16"
                    placeholder={selectedImage ? "Что изображено на картинке?.." : "Например: 'Шкаф 2м с ящиками'..."}
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    disabled={isLoading}
                />
                
                {/* Image Upload Triggers */}
                <div className="absolute right-2 bottom-4 flex gap-1">
                    {/* File Upload */}
                    <input 
                        type="file" 
                        ref={fileInputRef}
                        onChange={handleImageSelect}
                        accept="image/*"
                        className="hidden"
                    />
                    <button 
                        onClick={() => fileInputRef.current?.click()}
                        className="text-slate-400 hover:text-indigo-600 transition p-1 hover:bg-indigo-50 rounded"
                        title="Загрузить файл"
                    >
                        <ImagePlus size={18} />
                    </button>

                    {/* Camera Capture (Mobile) */}
                    <input 
                        type="file" 
                        ref={cameraInputRef}
                        onChange={handleImageSelect}
                        accept="image/*"
                        capture="environment"
                        className="hidden"
                    />
                    <button 
                        onClick={() => cameraInputRef.current?.click()}
                        className="text-slate-400 hover:text-indigo-600 transition p-1 hover:bg-indigo-50 rounded"
                        title="Сделать фото"
                    >
                        <Camera size={18} />
                    </button>
                </div>
            </div>

            <div className="flex gap-2">
                <button
                onClick={handleGenerate}
                disabled={isLoading || !prompt || !!selectedImage}
                className="flex-1 py-2 bg-indigo-600 text-white rounded text-xs font-bold hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-1 transition-colors shadow-md"
                >
                {isLoading ? <Loader2 className="animate-spin" size={14} /> : <><Wand2 size={14}/> Сгенерировать</>}
                </button>
                <button
                onClick={handleAskExpert}
                disabled={isLoading || (!prompt && !selectedImage)}
                className="flex-1 py-2 bg-amber-600 text-white rounded text-xs font-bold hover:bg-amber-700 disabled:opacity-50 flex items-center justify-center gap-1 transition-colors shadow-md"
                >
                {isLoading ? <Loader2 className="animate-spin" size={14} /> : <><BookOpen size={14}/> {selectedImage ? 'Анализ фото' : 'Спросить'}</>}
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
