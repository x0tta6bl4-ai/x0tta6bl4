
import React, { useId } from 'react';
import { Panel, EdgeThickness } from '../types';

interface PanelDrawingProps {
  panel: Panel;
  width: number;
  height: number;
  detailed?: boolean;
}

const PanelDrawing: React.FC<PanelDrawingProps> = ({ panel, width, height, detailed = false }) => {
  const uniqueId = useId().replace(/:/g, ''); 
  const markerId = `arrowhead-${uniqueId}`;
  const hatchId = `hatch-${uniqueId}`;
  
  // Increase padding for detailed view to accommodate outside dimensions
  const padding = detailed ? 100 : 30;
  
  // Cut Size calculation
  const getCutSize = (size: number, e1: EdgeThickness, e2: EdgeThickness) => {
      const t1 = e1 === '0.4' ? 0.4 : e1 === '2.0' ? 2 : 0;
      const t2 = e2 === '0.4' ? 0.4 : e2 === '2.0' ? 2 : 0;
      return size - t1 - t2;
  };
  
  const cutW = getCutSize(panel.width, panel.edging.left, panel.edging.right);
  const cutH = getCutSize(panel.height, panel.edging.top, panel.edging.bottom);

  // Scaling
  const availableW = width - (padding * 2);
  const availableH = height - (padding * 2);
  
  const scaleW = availableW / panel.width;
  const scaleH = availableH / panel.height;
  const scale = Math.min(scaleW, scaleH);

  const drawW = panel.width * scale;
  const drawH = panel.height * scale;
  
  const startX = (width - drawW) / 2;
  const startY = (height - drawH) / 2;

  const renderEdgeLine = (side: 'top' | 'bottom' | 'left' | 'right', type: EdgeThickness) => {
      if (type === 'none') return null;
      const color = type === '0.4' ? '#2563eb' : '#dc2626'; 
      const strokeWidth = type === '0.4' ? 2 : 4;
      
      let x1=0, y1=0, x2=0, y2=0;
      let tx=0, ty=0, rot=0;

      if(side === 'top') { 
          x1=startX; y1=startY; x2=startX+drawW; y2=startY; 
          tx=startX+drawW/2; ty=startY-8; 
      }
      if(side === 'bottom') { 
          x1=startX; y1=startY+drawH; x2=startX+drawW; y2=startY+drawH; 
          tx=startX+drawW/2; ty=startY+drawH+12; 
      }
      if(side === 'left') { 
          x1=startX; y1=startY; x2=startX; y2=startY+drawH; 
          tx=startX-12; ty=startY+drawH/2; rot=-90; 
      }
      if(side === 'right') { 
          x1=startX+drawW; y1=startY; x2=startX+drawW; y2=startY+drawH; 
          tx=startX+drawW+8; ty=startY+drawH/2; rot=-90; 
      }

      return (
          <g>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={strokeWidth} strokeLinecap="square" />
              {detailed && (
                  <text 
                    x={tx} y={ty} 
                    transform={rot ? `rotate(${rot}, ${tx}, ${ty})` : undefined} 
                    textAnchor="middle" 
                    fill={color} 
                    fontSize="9" 
                    fontWeight="bold"
                  >
                      {type}mm
                  </text>
              )}
          </g>
      );
  };

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} className="font-mono text-xs select-none bg-white">
        <defs>
            <marker id={markerId} markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#333" />
            </marker>
            <pattern id={hatchId} patternUnits="userSpaceOnUse" width="4" height="4" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="4" stroke="#000000" strokeWidth="1" opacity="0.5"/>
            </pattern>
        </defs>

        {/* Part Body */}
        <rect x={startX} y={startY} width={drawW} height={drawH} fill="#fff" stroke="#333" strokeWidth="2" />
        
        {/* Axis Lines (Center) */}
        {detailed && (
            <g opacity="0.3">
                <line x1={startX - 20} y1={startY + drawH/2} x2={startX + drawW + 20} y2={startY + drawH/2} stroke="#000" strokeWidth="0.5" strokeDasharray="10,5,2,5" />
                <line x1={startX + drawW/2} y1={startY - 20} x2={startX + drawW/2} y2={startY + drawH + 20} stroke="#000" strokeWidth="0.5" strokeDasharray="10,5,2,5" />
            </g>
        )}

        {/* Base Point Indicator */}
        <g transform={`translate(${startX - 15}, ${startY + drawH + 15})`}>
            <circle cx="0" cy="0" r="6" stroke="black" strokeWidth="1" fill="white"/>
            <path d="M-6,0 A6,6 0 0,0 0,6 L0,0 Z" fill="black"/>
            <path d="M0,-6 A6,6 0 0,1 6,0 L0,0 Z" fill="black"/>
            {detailed && <text x="10" y="4" fontSize="10" fontWeight="bold">БАЗА</text>}
        </g>

        {/* Grain direction */}
        {panel.textureRotation === 90 ? (
            <>
                    <line x1={startX + drawW/2 - 30} y1={startY + drawH/2} x2={startX + drawW/2 + 30} y2={startY + drawH/2} stroke="#94a3b8" strokeWidth="3" strokeDasharray="8,4" markerEnd={`url(#${markerId})`} />
                    {detailed && <text x={startX + drawW/2} y={startY + drawH/2 - 8} fill="#94a3b8" fontSize="10" fontWeight="bold" textAnchor="middle">Текстура</text>}
            </>
        ) : (
            <>
                <line x1={startX + drawW/2} y1={startY + drawH/2 - 30} x2={startX + drawW/2} y2={startY + drawH/2 + 30} stroke="#94a3b8" strokeWidth="3" strokeDasharray="8,4" markerEnd={`url(#${markerId})`} />
                {detailed && <text x={startX + drawW/2 + 8} y={startY + drawH/2} fill="#94a3b8" fontSize="10" fontWeight="bold">Текстура</text>}
            </>
        )}

        {/* Holes */}
        {(panel.hardware || []).map((hw, i) => {
            const cx = startX + hw.x * scale;
            const cy = startY + (panel.height - hw.y) * scale;
            
            // Determine "nearest edge" for minifix arrow direction
            const distL = hw.x;
            const distR = panel.width - hw.x;
            const distB = hw.y;
            const distT = panel.height - hw.y;
            const minDist = Math.min(distL, distR, distB, distT);
            
            let arrowRot = 0;
            if(minDist === distL) arrowRot = 180;
            if(minDist === distR) arrowRot = 0;
            if(minDist === distT) arrowRot = -90;
            if(minDist === distB) arrowRot = 90;

            return (
            <g key={hw.id || i}>
                {/* Center mark */}
                <line x1={cx - 3} y1={cy} x2={cx + 3} y2={cy} stroke="#ef4444" strokeWidth="0.5" />
                <line x1={cx} y1={cy - 3} x2={cx} y2={cy + 3} stroke="#ef4444" strokeWidth="0.5" />
                
                {/* SYMBOLS */}
                {hw.type === 'screw' && (
                    <g>
                        {/* Cross for through-hole screw */}
                        <line x1={cx-3} y1={cy-3} x2={cx+3} y2={cy+3} stroke="#ef4444" strokeWidth="1.5"/>
                        <line x1={cx+3} y1={cy-3} x2={cx-3} y2={cy+3} stroke="#ef4444" strokeWidth="1.5"/>
                        <circle cx={cx} cy={cy} r="3" stroke="#ef4444" fill="none" strokeWidth="1" />
                    </g>
                )}
                
                {hw.type === 'minifix_cam' && (
                    <g>
                        {/* Circle with arrow pointing to edge */}
                        <circle cx={cx} cy={cy} r="7.5" stroke="#ef4444" fill="none" strokeWidth="1.5" />
                        <g transform={`translate(${cx},${cy}) rotate(${arrowRot})`}>
                            <line x1="0" y1="0" x2="10" y2="0" stroke="#ef4444" strokeWidth="1"/>
                            <path d="M10,0 L7,-2 L7,2 Z" fill="#ef4444"/>
                        </g>
                    </g>
                )}
                
                {hw.type === 'dowel' && (
                    <g>
                        {/* Filled circle for dowel */}
                        <circle cx={cx} cy={cy} r="4" stroke="#ef4444" fill="#ef4444" />
                    </g>
                )}

                {(hw.type === 'handle' || hw.type === 'shelf_support') && (
                     <g>
                        <circle cx={cx} cy={cy} r="2.5" stroke="#ef4444" fill="white" strokeWidth="1.5" />
                    </g>
                )}
                
                {/* Label */}
                {detailed && (
                    <>
                        <circle cx={cx + 8} cy={cy - 8} r="6" fill="white" stroke="#666" strokeWidth="0.5"/>
                        <text x={cx + 8} y={cy - 5} textAnchor="middle" fontSize="8" fill="#333">{i+1}</text>
                    </>
                )}
                
                {/* Dimensions to Base */}
                {detailed && (
                    <>
                        {/* X Dimension */}
                        <line x1={cx} y1={cy} x2={cx} y2={startY + drawH + 20} stroke="#ccc" strokeDasharray="2,2" strokeWidth="0.5"/>
                        <text x={cx} y={startY + drawH + 30} textAnchor="middle" fontSize="9" fill="#000" fontWeight="bold">{Math.round(hw.x)}</text>
                        
                        {/* Y Dimension */}
                        <line x1={cx} y1={cy} x2={startX - 20} y2={cy} stroke="#ccc" strokeDasharray="2,2" strokeWidth="0.5"/>
                        <text x={startX - 25} y={cy + 3} textAnchor="end" fontSize="9" fill="#000" fontWeight="bold">{Math.round(hw.y)}</text>
                    </>
                )}
            </g>
        )})}

        {/* Edging */}
        {renderEdgeLine('top', panel.edging.top)}
        {renderEdgeLine('bottom', panel.edging.bottom)}
        {renderEdgeLine('left', panel.edging.left)}
        {renderEdgeLine('right', panel.edging.right)}

        {/* Grooves */}
        {panel.groove && panel.groove.enabled && (
            <g>
                {/* Draw groove lines depending on side */}
                {/* Top/Bottom grooves are horizontal */}
                {['top', 'bottom'].includes(panel.groove.side) && (
                    <>
                        <rect 
                            x={startX} 
                            y={panel.groove.side === 'top' ? startY + panel.groove.offset * scale : startY + drawH - (panel.groove.offset + panel.groove.width) * scale} 
                            width={drawW} 
                            height={panel.groove.width * scale} 
                            fill="url(#hatch)" 
                            stroke="#2563eb" 
                            strokeWidth="1" 
                            strokeDasharray="3,3"
                        />
                        {detailed && (
                            <g>
                                {/* Groove Dimension Labels */}
                                {panel.groove.side === 'top' ? (
                                    <>
                                        <text x={startX - 5} y={startY + (panel.groove.offset + panel.groove.width/2) * scale} textAnchor="end" fontSize="8" fill="#2563eb">Паз {panel.groove.width}x{panel.groove.depth}</text>
                                        <text x={startX - 5} y={startY + panel.groove.offset * scale} textAnchor="end" fontSize="8" fill="#2563eb">Ot {panel.groove.offset}</text>
                                    </>
                                ) : (
                                    <>
                                        <text x={startX - 5} y={startY + drawH - (panel.groove.offset + panel.groove.width/2) * scale} textAnchor="end" fontSize="8" fill="#2563eb">Паз {panel.groove.width}x{panel.groove.depth}</text>
                                        <text x={startX - 5} y={startY + drawH - panel.groove.offset * scale} textAnchor="end" fontSize="8" fill="#2563eb">Ot {panel.groove.offset}</text>
                                    </>
                                )}
                            </g>
                        )}
                    </>
                )}
                
                {/* Left/Right grooves are vertical */}
                {['left', 'right'].includes(panel.groove.side) && (
                    <>
                        <rect 
                            x={panel.groove.side === 'left' ? startX + panel.groove.offset * scale : startX + drawW - (panel.groove.offset + panel.groove.width) * scale} 
                            y={startY} 
                            width={panel.groove.width * scale} 
                            height={drawH} 
                            fill="url(#hatch)" 
                            stroke="#2563eb" 
                            strokeWidth="1" 
                            strokeDasharray="3,3"
                        />
                        {detailed && (
                            <g>
                                {panel.groove.side === 'left' ? (
                                    <text x={startX + (panel.groove.offset + panel.groove.width/2) * scale} y={startY - 5} textAnchor="middle" fontSize="8" fill="#2563eb" transform={`rotate(-90, ${startX + (panel.groove.offset + panel.groove.width/2) * scale}, ${startY - 5})`}>Паз {panel.groove.width}x{panel.groove.depth}</text>
                                ) : (
                                    <text x={startX + drawW - (panel.groove.offset + panel.groove.width/2) * scale} y={startY - 5} textAnchor="middle" fontSize="8" fill="#2563eb" transform={`rotate(-90, ${startX + drawW - (panel.groove.offset + panel.groove.width/2) * scale}, ${startY - 5})`}>Паз {panel.groove.width}x{panel.groove.depth}</text>
                                )}
                            </g>
                        )}
                    </>
                )}
            </g>
        )}

        {/* Main Dimensions */}
        <g transform={`translate(0, -${detailed ? 35 : 15})`}>
            <line x1={startX} y1={startY} x2={startX + drawW} y2={startY} stroke="#333" strokeWidth="1" markerStart={`url(#${markerId})`} markerEnd={`url(#${markerId})`} />
            <line x1={startX} y1={startY + 5} x2={startX} y2={startY - 5} stroke="#333"/>
            <line x1={startX + drawW} y1={startY + 5} x2={startX + drawW} y2={startY - 5} stroke="#333"/>
            <rect x={startX + drawW/2 - 25} y={startY - 10} width="50" height="18" fill="white" stroke="none"/>
            <text x={startX + drawW/2} y={startY + 3} textAnchor="middle" fill="#333" fontWeight="bold" fontSize="14">{panel.width}</text>
        </g>

        <g transform={`translate(-${detailed ? 35 : 15}, 0)`}>
            <line x1={startX} y1={startY} x2={startX} y2={startY + drawH} stroke="#333" strokeWidth="1" markerStart={`url(#${markerId})`} markerEnd={`url(#${markerId})`} />
            <line x1={startX - 5} y1={startY} x2={startX + 5} y2={startY} stroke="#333"/>
            <line x1={startX - 5} y1={startY + drawH} x2={startX + drawH} y2={startY + drawH} stroke="#333"/>
            <rect x={startX - 10} y={startY + drawH/2 - 12} width="20" height="24" fill="white" stroke="none"/>
            <text x={startX} y={startY + drawH/2 + 3} textAnchor="middle" transform={`rotate(-90, ${startX}, ${startY + drawH/2})`} fill="#333" fontWeight="bold" fontSize="14">{panel.height}</text>
        </g>

        {/* Legend */}
        {detailed && (
            <g transform={`translate(20, ${height - 120})`}>
                    <text x="0" y="0" fontSize="11" fontWeight="bold" fill="#333">Условные обозначения:</text>
                    
                    <g transform="translate(0, 15)">
                        <line x1="7" y1="-3" x2="13" y2="3" stroke="#ef4444" strokeWidth="1.5"/>
                        <line x1="13" y1="-3" x2="7" y2="3" stroke="#ef4444" strokeWidth="1.5"/>
                        <circle cx="10" cy="0" r="3" stroke="#ef4444" fill="none" strokeWidth="1" />
                        <text x="25" y="3" fontSize="9">Винт (Сквозное)</text>
                    </g>

                    <g transform="translate(0, 30)">
                        <circle cx="10" cy="0" r="7.5" stroke="#ef4444" fill="none" strokeWidth="1.5" />
                        <line x1="10" y1="0" x2="20" y2="0" stroke="#ef4444" strokeWidth="1"/>
                        <path d="M20,0 L17,-2 L17,2 Z" fill="#ef4444" transform="translate(0,0)"/>
                        <text x="35" y="3" fontSize="9">Эксцентрик D15</text>
                    </g>

                    <g transform="translate(0, 45)">
                        <circle cx="10" cy="0" r="4" stroke="#ef4444" fill="#ef4444"/>
                        <text x="25" y="3" fontSize="9">Шкант (Глухое)</text>
                    </g>
            </g>
        )}

        {/* Stamp */}
        {detailed && (
            <g transform={`translate(${width - 220}, ${height - 90})`}>
                <rect width="210" height="80" fill="none" stroke="#333" strokeWidth="1" />
                <line x1="0" y1="20" x2="210" y2="20" stroke="#333" strokeWidth="0.5"/>
                <line x1="0" y1="40" x2="210" y2="40" stroke="#333" strokeWidth="0.5"/>
                <line x1="0" y1="60" x2="210" y2="60" stroke="#333" strokeWidth="0.5"/>
                <line x1="70" y1="0" x2="70" y2="80" stroke="#333" strokeWidth="0.5"/>
                
                <text x="5" y="14" fontSize="9" fill="#666">Имя:</text>
                <text x="75" y="14" fontSize="10" fontWeight="bold">{panel.name.slice(0,25)}</text>
                
                <text x="5" y="34" fontSize="9" fill="#666">Мат:</text>
                <text x="75" y="34" fontSize="9">{panel.materialId}</text>
                
                <text x="5" y="54" fontSize="9" fill="#666">Габарит:</text>
                <text x="75" y="54" fontSize="9">{panel.width} x {panel.height}</text>

                <text x="5" y="74" fontSize="9" fill="#666">Пильный:</text>
                <text x="75" y="74" fontSize="9" fontWeight="bold">{cutW.toFixed(1)} x {cutH.toFixed(1)}</text>
            </g>
        )}
    </svg>
  );
};

export default PanelDrawing;
