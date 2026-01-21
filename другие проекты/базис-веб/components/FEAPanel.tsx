/**
 * FEAPanel Component
 * Панель для проведения конечно-элементного анализа (FEA)
 */

import React, { useState } from 'react';
import { FEAResult, ModalAnalysisResult } from '../types/CADTypes';

interface FEAPanelProps {
  isAnalyzing?: boolean;
  result: FEAResult | null;
  modalResult: ModalAnalysisResult | null;
  onRunAnalysis?: () => void;
  onRunModalAnalysis?: () => void;
  onExportResults?: (format: 'csv' | 'vtk' | 'paraview') => void;
}

type AnalysisType = 'linear' | 'modal';

/**
 * Компонент для проведения FEA анализа
 */
export const FEAPanel: React.FC<FEAPanelProps> = ({
  isAnalyzing = false,
  result,
  modalResult,
  onRunAnalysis,
  onRunModalAnalysis,
  onExportResults
}) => {
  const [activeTab, setActiveTab] = useState<AnalysisType>('linear');
  const [showVisualization, setShowVisualization] = useState(false);
  
  return (
    <div className="fea-panel">
      <div className="fea-header">
        <h3>Конечно-элементный анализ (FEA)</h3>
      </div>
      
      <div className="fea-tabs">
        <button
          className={`tab-btn ${activeTab === 'linear' ? 'active' : ''}`}
          onClick={() => setActiveTab('linear')}
        >
          Линейный статический анализ
        </button>
        <button
          className={`tab-btn ${activeTab === 'modal' ? 'active' : ''}`}
          onClick={() => setActiveTab('modal')}
        >
          Модальный анализ
        </button>
      </div>
      
      <div className="fea-content">
        {activeTab === 'linear' && (
          <div className="linear-analysis">
            <div className="controls">
              <button
                className="run-btn"
                onClick={onRunAnalysis}
                disabled={isAnalyzing}
              >
                {isAnalyzing ? 'Анализирую...' : 'Запустить анализ'}
              </button>
            </div>
            
            {result && (
              <div className="results">
                <h4>Результаты линейного анализа</h4>
                
                {/* TODO: Реализовать визуализацию результатов */}
                
                <div className="result-grid">
                  <div className="result-card">
                    <label>Макс. напряжение (Von Mises)</label>
                    <span>{result.maxStress?.toFixed(2) || 'N/A'} MPa</span>
                  </div>
                  
                  <div className="result-card">
                    <label>Макс. смещение</label>
                    <span>{result.maxDisplacement?.toFixed(4) || 'N/A'} mm</span>
                  </div>
                  
                  <div className="result-card">
                    <label>Коэффициент безопасности</label>
                    <span>{result.safetyFactor?.toFixed(2) || 'N/A'}</span>
                  </div>
                  
                  <div className="result-card">
                    <label>Состояние</label>
                    <span className={result.safetyFactor && result.safetyFactor > 1 ? 'safe' : 'unsafe'}>
                      {result.safetyFactor && result.safetyFactor > 1 ? 'OK ✓' : 'КРИТИЧНО ✗'}
                    </span>
                  </div>
                </div>
                
                {onExportResults && (
                  <div className="export-controls">
                    <button onClick={() => onExportResults('csv')}>Экспорт CSV</button>
                    <button onClick={() => onExportResults('vtk')}>Экспорт VTK</button>
                    <button onClick={() => onExportResults('paraview')}>ParaView</button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'modal' && (
          <div className="modal-analysis">
            <div className="controls">
              <button
                className="run-btn"
                onClick={onRunModalAnalysis}
                disabled={isAnalyzing}
              >
                {isAnalyzing ? 'Анализирую...' : 'Запустить модальный анализ'}
              </button>
            </div>
            
            {modalResult && (
              <div className="results">
                <h4>Результаты модального анализа</h4>
                
                <div className="modes-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Мода</th>
                        <th>Частота (Hz)</th>
                        <th>Период (s)</th>
                        <th>Участие массы (%)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {modalResult.modes?.map((mode, idx) => (
                        <tr key={idx}>
                          <td>{idx + 1}</td>
                          <td>{mode.frequency.toFixed(2)}</td>
                          <td>{(1 / mode.frequency).toFixed(4)}</td>
                          <td>{((idx + 1) * 10).toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                
                {onExportResults && (
                  <div className="export-controls">
                    <button onClick={() => onExportResults('csv')}>Экспорт CSV</button>
                    <button onClick={() => onExportResults('paraview')}>ParaView</button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      
      <style>{`
        .fea-panel {
          border: 1px solid #ddd;
          border-radius: 4px;
          padding: 16px;
          background: white;
        }
        .fea-header h3 {
          margin: 0 0 16px 0;
        }
        .fea-tabs {
          display: flex;
          gap: 8px;
          margin-bottom: 16px;
          border-bottom: 2px solid #eee;
        }
        .tab-btn {
          padding: 10px 16px;
          background: none;
          border: none;
          cursor: pointer;
          border-bottom: 3px solid transparent;
          font-weight: 500;
          color: #666;
          transition: all 0.2s;
        }
        .tab-btn:hover {
          color: #333;
        }
        .tab-btn.active {
          color: #2196f3;
          border-bottom-color: #2196f3;
        }
        .fea-content {
          margin-top: 16px;
        }
        .controls {
          margin-bottom: 16px;
        }
        .run-btn {
          padding: 8px 16px;
          background: #2196f3;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-weight: 500;
        }
        .run-btn:hover:not(:disabled) {
          background: #1976d2;
        }
        .run-btn:disabled {
          background: #ccc;
          cursor: not-allowed;
        }
        .result-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 12px;
          margin: 16px 0;
        }
        .result-card {
          border: 1px solid #eee;
          border-radius: 4px;
          padding: 12px;
          background: #f9f9f9;
        }
        .result-card label {
          display: block;
          font-size: 12px;
          color: #666;
          margin-bottom: 4px;
        }
        .result-card value {
          display: block;
          font-size: 18px;
          font-weight: bold;
          color: #333;
        }
        .result-card value.safe {
          color: #4caf50;
        }
        .result-card value.unsafe {
          color: #f44336;
        }
        .modes-table {
          overflow-x: auto;
          margin: 16px 0;
        }
        .modes-table table {
          width: 100%;
          border-collapse: collapse;
        }
        .modes-table th,
        .modes-table td {
          border: 1px solid #ddd;
          padding: 8px;
          text-align: right;
        }
        .modes-table th {
          background: #f5f5f5;
          font-weight: 600;
        }
        .export-controls {
          display: flex;
          gap: 8px;
          margin-top: 16px;
        }
        .export-controls button {
          padding: 6px 12px;
          background: #f5f5f5;
          border: 1px solid #ddd;
          border-radius: 4px;
          cursor: pointer;
          font-size: 13px;
        }
        .export-controls button:hover {
          background: #efefef;
        }
      `}</style>
    </div>
  );
};
