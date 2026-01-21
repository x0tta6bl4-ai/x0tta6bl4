/**
 * BOMViewer Component
 * Отображение спецификации материалов и стоимостей (Phase 3)
 */

import React, { useState, useMemo } from 'react';
import { BOMReport, BOMItem, BOMMaterial } from '../services/BillOfMaterials';

interface BOMViewerProps {
  bomReport: BOMReport | null;
  onExport?: (format: 'csv' | 'json' | 'html') => void;
  sortBy?: 'name' | 'cost' | 'mass' | 'volume';
}

type SortField = 'name' | 'cost' | 'mass' | 'volume' | 'material';

/**
 * Компонент для отображения спецификации материалов (Bill of Materials)
 */
export const BOMViewer: React.FC<BOMViewerProps> = ({ bomReport, onExport, sortBy = 'name' }) => {
  const [sortField, setSortField] = useState<SortField>(sortBy as SortField);
  const [sortDesc, setSortDesc] = useState(false);
  const [activeTab, setActiveTab] = useState<'items' | 'materials'>('items');

  const sortedItems = useMemo(() => {
    if (!bomReport) return [];

    const items = [...bomReport.items];
    items.sort((a, b) => {
      let aVal: any = a[sortField as keyof BOMItem];
      let bVal: any = b[sortField as keyof BOMItem];

      if (sortField === 'name') {
        aVal = a.componentName;
        bVal = b.componentName;
      }

      if (typeof aVal === 'string') {
        return sortDesc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
      }
      return sortDesc ? (bVal || 0) - (aVal || 0) : (aVal || 0) - (bVal || 0);
    });

    return items;
  }, [bomReport, sortField, sortDesc]);

  const sortedMaterials = useMemo(() => {
    if (!bomReport) return [];

    const materials = [...bomReport.materials];
    materials.sort((a, b) => {
      let aVal: any = a[sortField as keyof BOMMaterial];
      let bVal: any = b[sortField as keyof BOMMaterial];

      if (sortField === 'name' || sortField === 'material') {
        aVal = a.materialName;
        bVal = b.materialName;
      }

      if (typeof aVal === 'string') {
        return sortDesc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
      }
      return sortDesc ? (bVal || 0) - (aVal || 0) : (aVal || 0) - (bVal || 0);
    });

    return materials;
  }, [bomReport, sortField, sortDesc]);

  if (!bomReport) {
    return (
      <div className="bom-viewer empty">
        <p>Нет данных спецификации</p>
      </div>
    );
  }

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDesc(!sortDesc);
    } else {
      setSortField(field);
      setSortDesc(false);
    }
  };

  return (
    <div className="bom-viewer">
      <div className="bom-header">
        <h3>Спецификация материалов</h3>
        <div className="bom-controls">
          {onExport && (
            <>
              <button onClick={() => onExport('csv')} className="export-btn">
                📄 CSV
              </button>
              <button onClick={() => onExport('json')} className="export-btn">
                📋 JSON
              </button>
              <button onClick={() => onExport('html')} className="export-btn">
                🌐 HTML
              </button>
            </>
          )}
        </div>
      </div>

      <div className="bom-summary">
        <div className="stat">
          <label>Компонентов:</label>
          <span>{bomReport.meta.totalComponents}</span>
        </div>
        <div className="stat">
          <label>Материалов:</label>
          <span>{bomReport.meta.totalUniqueMaterials}</span>
        </div>
        <div className="stat">
          <label>Общая масса:</label>
          <span>{bomReport.meta.totalMass.toFixed(2)} кг</span>
        </div>
        <div className="stat">
          <label>Общий объём:</label>
          <span>{bomReport.meta.totalVolume.toFixed(6)} м³</span>
        </div>
        <div className="stat">
          <label>Общая стоимость:</label>
          <span className="cost">₽{bomReport.meta.totalCost.toFixed(2)}</span>
        </div>
        <div className="stat">
          <label>Время производства:</label>
          <span>{(bomReport.meta.totalProductionTime / 60).toFixed(1)} ч</span>
        </div>
      </div>

      <div className="bom-tabs">
        <button
          className={`tab ${activeTab === 'items' ? 'active' : ''}`}
          onClick={() => setActiveTab('items')}
        >
          Компоненты ({bomReport.items.length})
        </button>
        <button
          className={`tab ${activeTab === 'materials' ? 'active' : ''}`}
          onClick={() => setActiveTab('materials')}
        >
          Материалы ({bomReport.materials.length})
        </button>
      </div>

      {activeTab === 'items' && (
        <div className="bom-table">
          <table>
            <thead>
              <tr>
                <th onClick={() => handleSort('name')}>
                  Компонент {sortField === 'name' && (sortDesc ? '↓' : '↑')}
                </th>
                <th onClick={() => handleSort('material')}>
                  Материал {sortField === 'material' && (sortDesc ? '↓' : '↑')}
                </th>
                <th onClick={() => handleSort('volume')}>
                  Объём м³ {sortField === 'volume' && (sortDesc ? '↓' : '↑')}
                </th>
                <th onClick={() => handleSort('mass')}>
                  Масса кг {sortField === 'mass' && (sortDesc ? '↓' : '↑')}
                </th>
                <th onClick={() => handleSort('cost')}>
                  Стоимость ₽ {sortField === 'cost' && (sortDesc ? '↓' : '↑')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedItems.map((item) => (
                <tr key={item.id}>
                  <td>{item.componentName}</td>
                  <td>{item.material}</td>
                  <td>{item.volume.toFixed(6)}</td>
                  <td>{item.mass.toFixed(2)}</td>
                  <td>₽{item.cost.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'materials' && (
        <div className="bom-table">
          <table>
            <thead>
              <tr>
                <th onClick={() => handleSort('material')}>
                  Материал {sortField === 'material' && (sortDesc ? '↓' : '↑')}
                </th>
                <th>Кол-во</th>
                <th onClick={() => handleSort('volume')}>
                  Общий объём м³ {sortField === 'volume' && (sortDesc ? '↓' : '↑')}
                </th>
                <th onClick={() => handleSort('mass')}>
                  Общая масса кг {sortField === 'mass' && (sortDesc ? '↓' : '↑')}
                </th>
                <th onClick={() => handleSort('cost')}>
                  Стоимость ₽ {sortField === 'cost' && (sortDesc ? '↓' : '↑')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedMaterials.map((material) => (
                <tr key={material.materialName}>
                  <td>{material.materialName}</td>
                  <td>{material.quantity}</td>
                  <td>{material.totalVolume.toFixed(6)}</td>
                  <td>{material.totalMass.toFixed(2)}</td>
                  <td>₽{material.totalCost.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <style>{`
        .bom-viewer {
          border: 1px solid #ddd;
          border-radius: 4px;
          padding: 12px;
          background: white;
        }
        .bom-viewer.empty {
          text-align: center;
          color: #999;
          padding: 20px;
        }
        .bom-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
          border-bottom: 2px solid #f0f0f0;
          padding-bottom: 8px;
        }
        .bom-header h3 {
          margin: 0;
          font-size: 16px;
          font-weight: 600;
        }
        .bom-controls {
          display: flex;
          gap: 8px;
        }
        .export-btn {
          background: #4CAF50;
          color: white;
          border: none;
          padding: 6px 12px;
          border-radius: 3px;
          cursor: pointer;
          font-size: 12px;
        }
        .export-btn:hover {
          background: #45a049;
        }
        .bom-summary {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 12px;
          margin-bottom: 16px;
          padding: 12px;
          background: #f9f9f9;
          border-radius: 3px;
        }
        .stat {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 13px;
        }
        .stat label {
          font-weight: 600;
          color: #555;
        }
        .stat span {
          color: #333;
          font-weight: 500;
        }
        .stat .cost {
          color: #d32f2f;
          font-weight: 700;
        }
        .bom-tabs {
          display: flex;
          gap: 8px;
          margin-bottom: 12px;
          border-bottom: 1px solid #ddd;
        }
        .tab {
          background: none;
          border: none;
          padding: 8px 12px;
          cursor: pointer;
          font-size: 13px;
          border-bottom: 2px solid transparent;
          color: #555;
        }
        .tab.active {
          border-bottom-color: #4CAF50;
          color: #4CAF50;
          font-weight: 600;
        }
        .bom-table {
          overflow-x: auto;
        }
        .bom-table table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }
        .bom-table th {
          background: #f5f5f5;
          padding: 10px;
          text-align: left;
          font-weight: 600;
          border-bottom: 2px solid #ddd;
          cursor: pointer;
          user-select: none;
        }
        .bom-table th:hover {
          background: #e8e8e8;
        }
        .bom-table td {
          padding: 8px 10px;
          border-bottom: 1px solid #f0f0f0;
        }
        .bom-table tr:hover {
          background: #fafafa;
        }
      `}</style>
    </div>
  );
};
