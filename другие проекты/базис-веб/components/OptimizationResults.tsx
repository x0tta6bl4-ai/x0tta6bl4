/**
 * OptimizationResults Component
 * Отображение результатов параметрической оптимизации
 */

import React, { useState } from 'react';
import { OptimizedConfig, OptimizationObjective } from '../types/CADTypes';

interface OptimizationResultsProps {
  results: OptimizedConfig[] | null;
  selectedIndex?: number;
  onSelectConfig?: (index: number) => void;
  onApplyConfig?: (config: OptimizedConfig) => void;
}

/**
 * Компонент для отображения результатов оптимизации
 */
export const OptimizationResults: React.FC<OptimizationResultsProps> = ({
  results,
  selectedIndex = 0,
  onSelectConfig,
  onApplyConfig
}) => {
  const [sortBy, setSortBy] = useState<'score' | 'cost' | 'weight'>('score');
  
  if (!results || results.length === 0) {
    return (
      <div className="optimization-results empty">
        <p>Результаты оптимизации отсутствуют</p>
      </div>
    );
  }
  
  const sortedResults = [...results].sort((a, b) => {
    // TODO: Реализовать сортировку результатов по разным критериям
    switch (sortBy) {
      case 'cost':
        return (a.improvements.costReduction || 0) - (b.improvements.costReduction || 0);
      case 'weight':
        return (a.improvements.weightReduction || 0) - (b.improvements.weightReduction || 0);
      case 'score':
      default:
        return (b.score || 0) - (a.score || 0);
    }
  });
  
  const selectedConfig = sortedResults[selectedIndex];
  
  return (
    <div className="optimization-results">
      <div className="results-header">
        <h3>Результаты оптимизации</h3>
        <div className="sort-controls">
          <label>Сортировать по:</label>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}>
            <option value="score">Рейтингу</option>
            <option value="cost">Стоимости</option>
            <option value="weight">Весу</option>
          </select>
        </div>
      </div>
      
      <div className="results-list">
        {sortedResults.map((config, idx) => (
          <div
            key={idx}
            className={`result-item ${selectedIndex === idx ? 'selected' : ''}`}
            onClick={() => onSelectConfig?.(idx)}
          >
            <div className="result-rank">#{idx + 1}</div>
            <div className="result-details">
              <div className="detail-row">
                <span className="label">Рейтинг:</span>
                <span className="value">{(config.score || 0).toFixed(2)}%</span>
              </div>
              <div className="detail-row">
                <span className="label">Стоимость:</span>
                <span className="value">${(config.improvements.costReduction || 0).toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="label">Вес:</span>
                <span className="value">{(config.improvements.weightReduction || 0).toFixed(2)} кг</span>
              </div>
            </div>
            {selectedIndex === idx && onApplyConfig && (
              <button 
                className="apply-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onApplyConfig(config);
                }}
              >
                Применить
              </button>
            )}
          </div>
        ))}
      </div>
      
      {selectedConfig && (
        <div className="config-details">
          <h4>Детали конфигурации #{selectedIndex + 1}</h4>
          <div className="details-content">
            {/* TODO: Отобразить детальную информацию о выбранной конфигурации */}
            <div className="detail-section">
              <h5>Параметры оптимизации</h5>
              <ul>
                <li>Снижение стоимости: {selectedConfig.improvements.costReduction.toFixed(2)}%</li>
                <li>Снижение веса: {selectedConfig.improvements.weightReduction.toFixed(2)}%</li>
                <li>Увеличение прочности: {selectedConfig.improvements.strengthIncrease.toFixed(2)}%</li>
              </ul>
            </div>
          </div>
        </div>
      )}
      
      <style>{`
        .optimization-results {
          border: 1px solid #ddd;
          border-radius: 4px;
          padding: 16px;
          background: white;
        }
        .results-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }
        .results-header h3 {
          margin: 0;
        }
        .sort-controls {
          display: flex;
          gap: 8px;
          align-items: center;
        }
        .sort-controls select {
          padding: 4px 8px;
          border: 1px solid #ddd;
          border-radius: 4px;
        }
        .results-list {
          display: grid;
          gap: 8px;
          max-height: 300px;
          overflow-y: auto;
          margin-bottom: 16px;
        }
        .result-item {
          display: flex;
          gap: 12px;
          padding: 12px;
          border: 1px solid #eee;
          border-radius: 4px;
          cursor: pointer;
          align-items: center;
          transition: all 0.2s;
        }
        .result-item:hover {
          background: #f5f5f5;
          border-color: #2196f3;
        }
        .result-item.selected {
          background: #e3f2fd;
          border-color: #2196f3;
          box-shadow: 0 2px 4px rgba(33, 150, 243, 0.2);
        }
        .result-rank {
          font-weight: bold;
          color: #2196f3;
          min-width: 40px;
        }
        .result-details {
          flex: 1;
          font-size: 13px;
        }
        .detail-row {
          display: flex;
          justify-content: space-between;
          margin: 2px 0;
        }
        .detail-row .label {
          color: #666;
        }
        .detail-row .value {
          font-weight: 600;
        }
        .apply-btn {
          padding: 6px 12px;
          background: #4caf50;
          color: white;
          border: none;
          border-radius: 3px;
          cursor: pointer;
        }
        .apply-btn:hover {
          background: #45a049;
        }
        .config-details {
          border-top: 1px solid #ddd;
          padding-top: 16px;
        }
        .config-details h4 {
          margin: 0 0 12px 0;
        }
        .details-content {
          font-size: 13px;
        }
        .detail-section {
          margin-bottom: 12px;
        }
        .detail-section h5 {
          margin: 8px 0 4px 0;
          color: #333;
        }
        .detail-section ul {
          margin: 4px 0;
          padding-left: 20px;
        }
        .detail-section li {
          margin: 2px 0;
          color: #666;
        }
      `}</style>
    </div>
  );
};
