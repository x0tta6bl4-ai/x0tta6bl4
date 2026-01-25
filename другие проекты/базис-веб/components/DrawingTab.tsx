import React, { useState, useMemo } from 'react';
import { Panel } from '../types';
import { TechnicalDrawing, ViewType, DrawEntity } from '../services/TechnicalDrawing';
import { useProjectStore } from '../store/projectStore';

/**
 * DrawingTab компонент для отображения технических чертежей (4-вид)
 * Интеграция TechnicalDrawing.ts в UI
 */
export const DrawingTab: React.FC = () => {
  const panels = useProjectStore(s => s.panels);
  const [selectedView, setSelectedView] = useState<ViewType>('front');
  const [scale, setScale] = useState(1);
  const [showDimensions, setShowDimensions] = useState(true);
  const [showHidden, setShowHidden] = useState(false);

  // Генерируем чертеж для выбранного вида
  const drawing = useMemo(() => {
    return TechnicalDrawing.generateView(panels, selectedView);
  }, [panels, selectedView]);

  // Фильтруем слои по настройкам видимости
  const filteredEntities = useMemo(() => {
    return drawing.filter(entity => {
      if (!showDimensions && entity.layer === 'dimension') return false;
      if (!showDimensions && entity.layer === 'annotation') return false;
      if (!showHidden && entity.layer === 'hidden') return false;
      return true;
    });
  }, [drawing, showDimensions, showHidden]);

  // Экспорт в PDF (placeholder)
  const handleExportPDF = async () => {
    try {
      const pdfData = TechnicalDrawing.exportToPDF(filteredEntities, selectedView);
      // TODO: Здесь будет логика экспорта PDF
      console.log('Экспорт PDF:', pdfData);
      alert('✅ PDF экспортирован (demo)');
    } catch (error) {
      console.error('Ошибка при экспорте PDF:', error);
    }
  };

  return (
    <div className="w-full h-full flex flex-col bg-slate-900 text-white">
      {/* Toolbar */}
      <div className="bg-slate-800 border-b border-slate-700 p-4 space-y-3">
        {/* Выбор вида (4-view) */}
        <div className="flex gap-2">
          {(['front', 'top', 'left', 'right'] as ViewType[]).map(view => (
            <button
              key={view}
              onClick={() => setSelectedView(view)}
              className={`px-4 py-2 rounded text-sm font-semibold transition ${
                selectedView === view
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              {view === 'front' && '📐 Вид спереди'}
              {view === 'top' && '⬜ Вид сверху'}
              {view === 'left' && '◀ Вид слева'}
              {view === 'right' && '▶ Вид справа'}
            </button>
          ))}
        </div>

        {/* Масштаб и опции */}
        <div className="flex gap-4 items-center">
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-400">Масштаб:</label>
            <input
              type="range"
              min="0.5"
              max="3"
              step="0.1"
              value={scale}
              onChange={(e) => setScale(parseFloat(e.target.value))}
              className="w-24"
            />
            <span className="text-xs text-slate-400">{(scale * 100).toFixed(0)}%</span>
          </div>

          {/* Toggle опции */}
          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={showDimensions}
              onChange={(e) => setShowDimensions(e.target.checked)}
              className="w-4 h-4"
            />
            <span>Размеры</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={showHidden}
              onChange={(e) => setShowHidden(e.target.checked)}
              className="w-4 h-4"
            />
            <span>Скрытые линии</span>
          </label>

          {/* Экспорт PDF */}
          <button
            onClick={handleExportPDF}
            className="ml-auto px-4 py-2 bg-green-600 hover:bg-green-700 rounded text-sm font-semibold transition"
          >
            📥 PDF
          </button>
        </div>
      </div>

      {/* Canvas для чертежа */}
      <div className="flex-1 overflow-auto bg-slate-950 p-8">
        <svg
          width={1200 * scale}
          height={800 * scale}
          viewBox="0 0 1200 800"
          className="mx-auto bg-white shadow-lg"
          style={{ minWidth: '100%', minHeight: '100%', objectFit: 'contain' }}
        >
          {/* Grid background */}
          <defs>
            <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
              <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#e5e5e5" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="1200" height="800" fill="url(#grid)" />

          {/* Отрисовка сущностей чертежа */}
          {filteredEntities.map((entity, idx) => {
            // Определяем цвет слоя
            const layerColors: Record<string, string> = {
              contour: '#000',
              hidden: '#999',
              dimension: '#0066cc',
              center: '#ff6600',
              annotation: '#339933'
            };

            switch (entity.type) {
              case 'line':
                return (
                  <line
                    key={idx}
                    x1={entity.x1}
                    y1={entity.y1}
                    x2={entity.x2}
                    y2={entity.y2}
                    stroke={layerColors[entity.layer] || '#000'}
                    strokeWidth={entity.dashed ? '2' : '1'}
                    strokeDasharray={entity.dashed ? '5,5' : 'none'}
                  />
                );

              case 'rect':
                return (
                  <rect
                    key={idx}
                    x={entity.x}
                    y={entity.y}
                    width={entity.w}
                    height={entity.h}
                    fill="none"
                    stroke={layerColors[entity.layer] || '#000'}
                    strokeWidth="1"
                  />
                );

              case 'text':
                return (
                  <text
                    key={idx}
                    x={entity.x}
                    y={entity.y}
                    fill={layerColors[entity.layer] || '#000'}
                    fontSize="10"
                    fontFamily="Arial"
                  >
                    {entity.text}
                  </text>
                );

              case 'dim_linear':
                return (
                  <g key={idx}>
                    <line
                      x1={entity.x1}
                      y1={entity.y1}
                      x2={entity.x2}
                      y2={entity.y2}
                      stroke="#0066cc"
                      strokeWidth="1"
                    />
                    <text
                      x={(entity.x1! + entity.x2!) / 2}
                      y={(entity.y1! + entity.y2!) / 2 - 5}
                      fill="#0066cc"
                      fontSize="10"
                      textAnchor="middle"
                    >
                      {entity.value}мм
                    </text>
                  </g>
                );

              default:
                return null;
            }
          })}
        </svg>
      </div>

      {/* Info bar */}
      <div className="bg-slate-800 border-t border-slate-700 p-3 text-xs text-slate-400">
        <span>📊 Вид: {selectedView} | 🔷 Элементов: {filteredEntities.length} | 📐 Панелей: {panels.length}</span>
      </div>
    </div>
  );
};

export default DrawingTab;
