/**
 * NEURAL GENERATION PANEL
 * 
 * Профессиональный UI для генерации 3D мебели из параметров
 * используя дообученную нейросеть
 */

import React, { useState, useEffect } from 'react';
import { NeuralCADGenerator, CabinetParametersForNeural, NeuralGeneratedShape, ModelStatus } from '../services/cad/NeuralCADGenerator';
import { useCADStore } from '../services/cad';

interface GenerationState {
  isLoading: boolean;
  isGenerating: boolean;
  generationProgress: number;
  lastGeneration: NeuralGeneratedShape | null;
  error: string | null;
  modelStatus: ModelStatus | null;
}

export function NeuralGenerationPanel() {
  const [generator] = useState(() => new NeuralCADGenerator());
  const [state, setState] = useState<GenerationState>({
    isLoading: true,
    isGenerating: false,
    generationProgress: 0,
    lastGeneration: null,
    error: null,
    modelStatus: null
  });
  
  // Параметры мебели
  const [params, setParams] = useState<CabinetParametersForNeural>({
    width: 1200,
    height: 1400,
    depth: 600,
    shelfCount: 3,
    shelfThickness: 16,
    edgeType: 1,
    materialDensity: 800,
    hasDrawers: 0,
    drawerCount: 0,
    doorType: 1,
    baseType: 0,
    customFeatures: 0,
    quality: 0.85
  });
  
  const { createModel, updateParameter } = useCADStore();
  
  // Инициализация нейросети
  useEffect(() => {
    const initializeGenerator = async () => {
      try {
        console.log('🤖 Инициализация Neural CAD Generator...');
        await generator.initialize();
        const status = generator.getStatus();
        
        setState(prev => ({
          ...prev,
          isLoading: false,
          modelStatus: status
        }));
        
        console.log('✅ Neural CAD Generator готов!');
      } catch (error) {
        setState(prev => ({
          ...prev,
          isLoading: false,
          error: `Failed to initialize neural model: ${error}`
        }));
        console.error('❌ Initialization error:', error);
      }
    };
    
    initializeGenerator();
  }, [generator]);
  
  /**
   * Основной метод: генерировать мебель
   */
  const handleGenerate = async () => {
    if (!generator.isReady()) {
      setState(prev => ({ ...prev, error: 'Neural model not loaded' }));
      return;
    }
    
    setState(prev => ({
      ...prev,
      isGenerating: true,
      generationProgress: 0,
      error: null
    }));
    
    try {
      console.log('🚀 Начало генерации 3D мебели из параметров...');
      
      // Генерировать с нейросетью
      const result = await generator.generate(params);
      
      console.log('✅ Генерация завершена!');
      console.log(`  - Вершины: ${result.metrics.vertexCount}`);
      console.log(`  - Грани: ${result.metrics.faceCount}`);
      console.log(`  - Время: ${result.generationTime.toFixed(0)}ms`);
      console.log(`  - Уверенность: ${(result.confidence * 100).toFixed(1)}%`);
      
      setState(prev => ({
        ...prev,
        isGenerating: false,
        generationProgress: 100,
        lastGeneration: result
      }));
      
      // Отправить событие в 3D вьювер
      window.dispatchEvent(new CustomEvent('neural-cabinet-generated', {
        detail: { geometry: result, parameters: params }
      }));
      
    } catch (error) {
      console.error('❌ Generation error:', error);
      setState(prev => ({
        ...prev,
        isGenerating: false,
        error: `Generation failed: ${error}`
      }));
    }
  };
  
  if (state.isLoading) {
    return (
      <div className="neural-panel loading">
        <div className="spinner"></div>
        <p>Loading neural model...</p>
      </div>
    );
  }
  
  return (
    <div className="neural-generation-panel">
      <style>{`
        .neural-generation-panel {
          width: 100%;
          height: 100%;
          background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
          color: #e0e0e0;
          font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
          display: flex;
          flex-direction: column;
          overflow-y: auto;
        }
        
        .neural-panel {
          padding: 20px;
        }
        
        .neural-panel.loading {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          gap: 20px;
          font-size: 18px;
        }
        
        .spinner {
          width: 40px;
          height: 40px;
          border: 4px solid #333;
          border-top-color: #00d4ff;
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        .panel-header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 24px;
          padding-bottom: 16px;
          border-bottom: 2px solid #00d4ff;
        }
        
        .panel-header h2 {
          margin: 0;
          font-size: 24px;
          font-weight: 600;
          color: #00d4ff;
        }
        
        .status-badge {
          display: inline-block;
          padding: 6px 12px;
          background: #4caf50;
          color: white;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 500;
        }
        
        .status-badge.loading {
          background: #ff9800;
        }
        
        .section {
          margin-bottom: 24px;
        }
        
        .section-title {
          font-size: 14px;
          font-weight: 600;
          color: #00d4ff;
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-bottom: 12px;
        }
        
        .param-group {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin-bottom: 12px;
        }
        
        .param-item {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        
        .param-label {
          font-size: 12px;
          font-weight: 500;
          color: #b0b0b0;
          display: flex;
          justify-content: space-between;
        }
        
        .param-value {
          color: #00d4ff;
          font-weight: 600;
        }
        
        .param-input {
          width: 100%;
          padding: 8px 12px;
          background: #0f3460;
          border: 1px solid #00d4ff;
          color: #e0e0e0;
          border-radius: 4px;
          font-size: 13px;
          font-family: monospace;
        }
        
        .param-input:focus {
          outline: none;
          border-color: #00ffff;
          box-shadow: 0 0 8px rgba(0, 212, 255, 0.3);
        }
        
        .slider-container {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        
        .param-slider {
          flex: 1;
          height: 4px;
          background: #0f3460;
          border-radius: 2px;
          outline: none;
          -webkit-appearance: none;
        }
        
        .param-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 16px;
          height: 16px;
          background: #00d4ff;
          border-radius: 50%;
          cursor: pointer;
          box-shadow: 0 0 8px rgba(0, 212, 255, 0.5);
        }
        
        .param-slider::-moz-range-thumb {
          width: 16px;
          height: 16px;
          background: #00d4ff;
          border: none;
          border-radius: 50%;
          cursor: pointer;
          box-shadow: 0 0 8px rgba(0, 212, 255, 0.5);
        }
        
        .slider-value {
          min-width: 50px;
          text-align: right;
          font-weight: 600;
          color: #00d4ff;
        }
        
        .generate-button {
          width: 100%;
          padding: 14px;
          background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
          color: #000;
          border: none;
          border-radius: 6px;
          font-size: 16px;
          font-weight: 700;
          cursor: pointer;
          text-transform: uppercase;
          letter-spacing: 1px;
          transition: all 0.3s ease;
          margin-bottom: 12px;
        }
        
        .generate-button:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 8px 24px rgba(0, 212, 255, 0.4);
        }
        
        .generate-button:active:not(:disabled) {
          transform: translateY(0);
        }
        
        .generate-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        
        .progress-bar {
          width: 100%;
          height: 6px;
          background: #0f3460;
          border-radius: 3px;
          overflow: hidden;
          margin-bottom: 12px;
        }
        
        .progress-fill {
          height: 100%;
          background: linear-gradient(90deg, #00d4ff 0%, #0099cc 100%);
          transition: width 0.3s ease;
        }
        
        .stats-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }
        
        .stat-card {
          background: rgba(0, 212, 255, 0.1);
          border: 1px solid rgba(0, 212, 255, 0.3);
          border-radius: 6px;
          padding: 12px;
          text-align: center;
        }
        
        .stat-label {
          font-size: 11px;
          color: #8a8a8a;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 6px;
        }
        
        .stat-value {
          font-size: 18px;
          font-weight: 700;
          color: #00d4ff;
        }
        
        .error-message {
          background: rgba(255, 76, 76, 0.1);
          border: 1px solid rgba(255, 76, 76, 0.5);
          color: #ff9999;
          padding: 12px;
          border-radius: 4px;
          font-size: 13px;
          margin-bottom: 12px;
        }
        
        .success-message {
          background: rgba(76, 175, 80, 0.1);
          border: 1px solid rgba(76, 175, 80, 0.5);
          color: #81c784;
          padding: 12px;
          border-radius: 4px;
          font-size: 13px;
          margin-bottom: 12px;
        }
        
        .model-info {
          background: rgba(0, 212, 255, 0.05);
          border: 1px solid rgba(0, 212, 255, 0.2);
          border-radius: 6px;
          padding: 12px;
          font-size: 12px;
          color: #b0b0b0;
          margin-top: 12px;
        }
        
        .model-info strong {
          color: #00d4ff;
        }
      `}</style>
      
      <div className="neural-panel">
        {/* Header */}
        <div className="panel-header">
          <span style={{ fontSize: '32px' }}>🤖</span>
          <h2>Neural Generator</h2>
          {generator.isReady() && (
            <div className="status-badge">READY</div>
          )}
        </div>
        
        {/* Error Messages */}
        {state.error && (
          <div className="error-message">
            ❌ {state.error}
          </div>
        )}
        
        {/* Success Message */}
        {state.lastGeneration && (
          <div className="success-message">
            ✅ 3D модель сгенерирована успешно!
            Уверенность: {(state.lastGeneration.confidence * 100).toFixed(1)}%
          </div>
        )}
        
        {/* Cabinet Parameters */}
        <div className="section">
          <div className="section-title">📐 Параметры мебели</div>
          
          <div className="param-group">
            <div className="param-item">
              <label className="param-label">
                Ширина (мм)
                <span className="param-value">{params.width}</span>
              </label>
              <input
                type="range"
                min="300"
                max="3000"
                value={params.width}
                onChange={(e) => setParams({ ...params, width: parseInt(e.target.value) })}
                className="param-slider"
              />
            </div>
            
            <div className="param-item">
              <label className="param-label">
                Высота (мм)
                <span className="param-value">{params.height}</span>
              </label>
              <input
                type="range"
                min="400"
                max="2500"
                value={params.height}
                onChange={(e) => setParams({ ...params, height: parseInt(e.target.value) })}
                className="param-slider"
              />
            </div>
          </div>
          
          <div className="param-group">
            <div className="param-item">
              <label className="param-label">
                Глубина (мм)
                <span className="param-value">{params.depth}</span>
              </label>
              <input
                type="range"
                min="300"
                max="1000"
                value={params.depth}
                onChange={(e) => setParams({ ...params, depth: parseInt(e.target.value) })}
                className="param-slider"
              />
            </div>
            
            <div className="param-item">
              <label className="param-label">
                Полок
                <span className="param-value">{params.shelfCount}</span>
              </label>
              <input
                type="range"
                min="0"
                max="10"
                value={params.shelfCount}
                onChange={(e) => setParams({ ...params, shelfCount: parseInt(e.target.value) })}
                className="param-slider"
              />
            </div>
          </div>
          
          <div className="param-group">
            <div className="param-item">
              <label className="param-label">Тип рёбер</label>
              <select
                value={params.edgeType}
                onChange={(e) => setParams({ ...params, edgeType: parseInt(e.target.value) as any })}
                className="param-input"
              >
                <option value="0">Острые</option>
                <option value="1">Скруглённые</option>
                <option value="2">Скошенные</option>
              </select>
            </div>
            
            <div className="param-item">
              <label className="param-label">Тип двери</label>
              <select
                value={params.doorType}
                onChange={(e) => setParams({ ...params, doorType: parseInt(e.target.value) as any })}
                className="param-input"
              >
                <option value="0">Нет</option>
                <option value="1">Распашная</option>
                <option value="2">Купе</option>
              </select>
            </div>
          </div>
        </div>
        
        {/* Generate Button */}
        <button
          className="generate-button"
          onClick={handleGenerate}
          disabled={state.isGenerating || !generator.isReady()}
        >
          {state.isGenerating ? '⏳ Генерирование...' : '✨ Сгенерировать 3D'}
        </button>
        
        {/* Progress */}
        {state.isGenerating && (
          <>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${state.generationProgress}%` }}></div>
            </div>
            <p style={{ textAlign: 'center', fontSize: '12px', color: '#8a8a8a' }}>
              Генерирование 3D модели...
            </p>
          </>
        )}
        
        {/* Statistics */}
        {state.lastGeneration && (
          <div className="section">
            <div className="section-title">📊 Статистика</div>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Вершины</div>
                <div className="stat-value">{state.lastGeneration.metrics.vertexCount}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Грани</div>
                <div className="stat-value">{state.lastGeneration.metrics.faceCount}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Время</div>
                <div className="stat-value">{state.lastGeneration.generationTime.toFixed(0)}ms</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Уверенность</div>
                <div className="stat-value">{(state.lastGeneration.confidence * 100).toFixed(1)}%</div>
              </div>
            </div>
          </div>
        )}
        
        {/* Model Info */}
        {state.modelStatus && (
          <div className="model-info">
            <strong>Model Info:</strong><br/>
            {state.modelStatus.name} v{state.modelStatus.version}<br/>
            Training data: {state.modelStatus.trainingDataSize.toLocaleString()} examples<br/>
            Accuracy: {(state.modelStatus.accuracy * 100).toFixed(1)}%
          </div>
        )}
      </div>
    </div>
  );
}

export default NeuralGenerationPanel;
