import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Panel } from '../../types';

interface CanvasEditorProps {
  panels: Panel[];
  selectedPanelId: string | null;
  onSelectPanel: (id: string) => void;
  onUpdatePanel: (id: string, changes: Partial<Panel>) => void;
  zoom: number;
  onZoomChange: (zoom: number) => void;
  gridSize: number;
  showGrid: boolean;
}

export const CanvasEditor: React.FC<CanvasEditorProps> = ({
  panels,
  selectedPanelId,
  onSelectPanel,
  onUpdatePanel,
  zoom,
  onZoomChange,
  gridSize,
  showGrid
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [offsetX, setOffsetX] = useState(0);
  const [offsetY, setOffsetY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredPanelId, setHoveredPanelId] = useState<string | null>(null);

  // Draw Grid
  const drawGrid = (ctx: CanvasRenderingContext2D, width: number, height: number) => {
    if (!showGrid) return;

    const scaledGridSize = (gridSize * zoom) / 100;
    ctx.strokeStyle = '#404854';
    ctx.lineWidth = 0.5;

    // Vertical lines
    let x = offsetX % scaledGridSize;
    while (x < width) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
      x += scaledGridSize;
    }

    // Horizontal lines
    let y = offsetY % scaledGridSize;
    while (y < height) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
      y += scaledGridSize;
    }
  };

  // Draw Panel
  const drawPanel = (
    ctx: CanvasRenderingContext2D,
    panel: Panel,
    isSelected: boolean,
    isHovered: boolean
  ) => {
    const scale = zoom / 100;
    const x = panel.x * scale + offsetX;
    const y = panel.y * scale + offsetY;
    const w = panel.width * scale;
    const h = panel.height * scale;

    // Fill
    if (isSelected) {
      ctx.fillStyle = '#3B82F6';
      ctx.globalAlpha = 0.7;
    } else if (isHovered) {
      ctx.fillStyle = '#60A5FA';
      ctx.globalAlpha = 0.6;
    } else {
      ctx.fillStyle = panel.color;
      ctx.globalAlpha = 0.8;
    }
    ctx.fillRect(x, y, w, h);
    ctx.globalAlpha = 1;

    // Stroke
    ctx.strokeStyle = isSelected ? '#3B82F6' : isHovered ? '#60A5FA' : '#94A3B8';
    ctx.lineWidth = isSelected ? 2 : 1;
    ctx.strokeRect(x, y, w, h);

    // Label (if zoomed in enough)
    if (zoom > 50) {
      ctx.fillStyle = isSelected || isHovered ? '#FFFFFF' : '#E2E8F0';
      ctx.font = `${12 * scale}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(panel.name, x + w / 2, y + h / 2);
    }
  };

  // Draw Canvas
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear
    ctx.fillStyle = '#0f0f0f';
    ctx.fillRect(0, 0, width, height);

    // Grid
    drawGrid(ctx, width, height);

    // Panels (sorted by layer)
    const layerOrder = ['back', 'shelves', 'body', 'facade'];
    const sortedPanels = [...panels].sort(
      (a, b) => layerOrder.indexOf(a.layer) - layerOrder.indexOf(b.layer)
    );

    sortedPanels.forEach((panel) => {
      const isSelected = panel.id === selectedPanelId;
      const isHovered = panel.id === hoveredPanelId;
      drawPanel(ctx, panel, isSelected, isHovered);
    });

    // Rulers
    drawRulers(ctx, width, height);
  }, [panels, selectedPanelId, hoveredPanelId, zoom, offsetX, offsetY, gridSize, showGrid]);

  const drawRulers = (ctx: CanvasRenderingContext2D, width: number, height: number) => {
    const rulerSize = 20;
    const scale = zoom / 100;

    // Ruler background
    ctx.fillStyle = '#1E293B';
    ctx.fillRect(0, 0, rulerSize, height);
    ctx.fillRect(0, 0, width, rulerSize);

    // Ruler text
    ctx.fillStyle = '#64748B';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // Vertical ruler
    for (let i = 0; i < height; i += 50 * scale) {
      ctx.fillText(`${Math.round(i / scale)}`, rulerSize / 2, rulerSize + i);
    }

    // Horizontal ruler
    for (let i = 0; i < width; i += 50 * scale) {
      ctx.fillText(`${Math.round(i / scale)}`, rulerSize + i, rulerSize / 2);
    }
  };

  // Render loop
  useEffect(() => {
    draw();
  }, [draw]);

  // Panel picking
  const getPanelAtPoint = (x: number, y: number): Panel | null => {
    const scale = zoom / 100;
    const canvasX = (x - offsetX) / scale;
    const canvasY = (y - offsetY) / scale;

    for (let i = panels.length - 1; i >= 0; i--) {
      const panel = panels[i];
      if (
        canvasX >= panel.x &&
        canvasX <= panel.x + panel.width &&
        canvasY >= panel.y &&
        canvasY <= panel.y + panel.height
      ) {
        return panel;
      }
    }
    return null;
  };

  // Mouse events
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (e.button === 2) {
      // Right-click: pan
      setIsDragging(true);
      setDragStart({ x, y });
    } else if (e.button === 0) {
      // Left-click: select
      const panel = getPanelAtPoint(x, y);
      if (panel) {
        onSelectPanel(panel.id);
      }
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (isDragging) {
      const dx = x - dragStart.x;
      const dy = y - dragStart.y;
      setOffsetX(offsetX + dx);
      setOffsetY(offsetY + dy);
      setDragStart({ x, y });
    } else {
      const panel = getPanelAtPoint(x, y);
      setHoveredPanelId(panel?.id || null);
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -10 : 10;
    onZoomChange(Math.max(10, Math.min(200, zoom + delta)));
  };

  return (
    <div className="relative w-full h-full bg-slate-950">
      <canvas
        ref={canvasRef}
        width={window.innerWidth - 320}
        height={window.innerHeight - 100}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onContextMenu={(e) => e.preventDefault()}
        onWheel={handleWheel}
        className="cursor-grab active:cursor-grabbing"
      />

      {/* Info Overlay */}
      <div className="absolute bottom-4 left-4 bg-black/50 text-slate-300 text-xs p-2 rounded border border-slate-600 pointer-events-none">
        <div>Zoom: {zoom}%</div>
        <div>Grid: {gridSize}mm</div>
        <div>Panels: {panels.length}</div>
      </div>
    </div>
  );
};
