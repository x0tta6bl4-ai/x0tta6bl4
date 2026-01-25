/**
 * DFMReport Component
 * Отображение результатов Design for Manufacturing анализа
 */

import React, { useMemo } from 'react';
import { DFMReport, DFMCheckResult, DFMSeverity } from '../types/CADTypes';

interface DFMReportProps {
  report: DFMReport | null;
  onApplySuggestion?: (suggestionId: string) => void;
}

/**
 * Получить цвет для уровня серьёзности
 */
const getSeverityColor = (severity: DFMSeverity): string => {
  switch (severity) {
    case DFMSeverity.ERROR: return '#f44336';
    case DFMSeverity.WARNING: return '#ff9800';
    case DFMSeverity.INFO: return '#2196f3';
    default: return '#999';
  }
};

/**
 * Компонент для отображения отчёта DFM анализа
 */
export const DFMReportComponent: React.FC<DFMReportProps> = ({ report, onApplySuggestion }) => {
  const statistics = useMemo(() => {
    if (!report) return null;

    const errors = report.errors?.length || 0;
    const warnings = report.warnings?.length || 0;
    const info = report.infos?.length || 0;

    return {
      errors,
      warnings,
      info
    };
  }, [report]);
  
  if (!report) {
    return (
      <div className="dfm-report empty">
        <p>Нет результатов анализа DFM</p>
      </div>
    );
  }
  
  const overallScore = report.manufacturability || 0;
  
  return (
    <div className="dfm-report">
      <div className="dfm-header">
        <h3>Design for Manufacturing Анализ</h3>
        <div className="dfm-score">
          <div className="score-circle" style={{
            borderColor: overallScore > 80 ? '#4caf50' : overallScore > 60 ? '#ff9800' : '#f44336'
          }}>
            {overallScore.toFixed(0)}%
          </div>
        </div>
      </div>
      
      <div className="dfm-stats">
        <div className="stat error">
          <span className="label">Ошибок:</span>
          <span className="value">{statistics?.errors || 0}</span>
        </div>
        <div className="stat warning">
          <span className="label">Предупреждений:</span>
          <span className="value">{statistics?.warnings || 0}</span>
        </div>
        <div className="stat info">
          <span className="label">Информация:</span>
          <span className="value">{statistics?.info || 0}</span>
        </div>
      </div>
      
      <div className="dfm-checks">
        {[...(report.errors || []), ...(report.warnings || []), ...(report.infos || [])].map((check, idx) => (
          <div key={idx} className="check-item" style={{
            borderLeft: `4px solid ${getSeverityColor(check.severity)}`
          }}>
            <div className="check-header">
              <span className="severity" style={{ color: getSeverityColor(check.severity) }}>
                {check.severity}
              </span>
              <span className="rule">{check.ruleId}</span>
            </div>
            <div className="check-message">{check.message}</div>
            {check.suggestion && (
              <div className="suggestions">
                <strong>Рекомендации:</strong>
                <ul>
                  <li>
                    {check.suggestion}
                    {onApplySuggestion && (
                      <button onClick={() => onApplySuggestion(check.ruleId)}>
                        Применить
                      </button>
                    )}
                  </li>
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
      
      <style>{`
        .dfm-report {
          border: 1px solid #ddd;
          border-radius: 4px;
          padding: 16px;
          background: white;
        }
        .dfm-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }
        .dfm-header h3 {
          margin: 0;
        }
        .score-circle {
          width: 80px;
          height: 80px;
          border: 4px solid;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 24px;
          font-weight: bold;
        }
        .dfm-stats {
          display: flex;
          gap: 16px;
          margin-bottom: 16px;
        }
        .stat {
          flex: 1;
          padding: 8px;
          border-radius: 4px;
          background: #f5f5f5;
        }
        .stat.error {
          background: #ffebee;
        }
        .stat.warning {
          background: #fff3e0;
        }
        .stat.info {
          background: #e3f2fd;
        }
        .stat .label {
          display: block;
          font-size: 12px;
          color: #666;
        }
        .stat .value {
          display: block;
          font-size: 20px;
          font-weight: bold;
        }
        .check-item {
          padding: 12px;
          margin-bottom: 8px;
          background: #f9f9f9;
          border-radius: 4px;
        }
        .check-header {
          display: flex;
          gap: 12px;
          margin-bottom: 4px;
        }
        .severity {
          font-weight: bold;
          font-size: 12px;
          text-transform: uppercase;
        }
        .rule {
          font-weight: 600;
        }
        .check-message {
          color: #666;
          margin: 4px 0;
          font-size: 14px;
        }
        .suggestions {
          margin-top: 8px;
          padding-top: 8px;
          border-top: 1px solid #ddd;
          font-size: 13px;
        }
        .suggestions ul {
          margin: 4px 0;
          padding-left: 20px;
        }
        .suggestions li {
          margin: 4px 0;
        }
        .suggestions button {
          margin-left: 8px;
          padding: 2px 8px;
          background: #2196f3;
          color: white;
          border: none;
          border-radius: 3px;
          cursor: pointer;
          font-size: 11px;
        }
      `}</style>
    </div>
  );
};

export default DFMReportComponent;
