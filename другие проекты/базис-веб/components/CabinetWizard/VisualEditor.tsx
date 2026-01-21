import React, { useState, useRef, useEffect } from 'react';
import { CabinetConfig, Section, CabinetItem } from '../../types';
import { useCabinetDragDrop } from '../../hooks/useCabinetDragDrop';
import { Plus, Trash2, GripVertical } from 'lucide-react';

interface VisualEditorProps {
  config: CabinetConfig;
  sections: Section[];
  selectedSectionId: number;
  selectedItemId: string | null;
  showDoors: boolean;
  onSelectSection: (id: number) => void;
  onSelectItem: (id: string | null) => void;
  onMoveItem: (itemId: string, targetSecIdx: number, newY: number) => void;
  onResizeSection: (index: number, delta: number) => void;
  onAddItem?: (type: CabinetItem['type']) => void;
  onAddSection?: () => void;
  onDeleteSelected?: () => void;
}

const VisualEditor = React.memo(({
  config,
  sections,
  selectedSectionId,
  selectedItemId,
  showDoors,
  onSelectSection,
  onSelectItem,
  onMoveItem,
  onResizeSection,
}: VisualEditorProps) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0.15);

  const { dragState, snapLine, startDrag, calculateTargetSection } = useCabinetDragDrop({
    config,
    sections,
    wrapperRef,
    scale,
    onMoveItem,
    onResizeSection,
  });

  useEffect(() => {
    if (!wrapperRef.current) return;
    const update = () => {
      const { clientWidth, clientHeight } = wrapperRef.current!;
      const padding = 100;
      const sX = (clientWidth - padding) / config.width;
      const sY = (clientHeight - padding) / config.height;
      setScale(Math.min(sX, sY));
    };
    const obs = new ResizeObserver(update);
    obs.observe(wrapperRef.current);
    update();
    return () => obs.disconnect();
  }, [config.width, config.height]);

  const renderDoors = () => {
    if (!showDoors || config.doorType === 'none') return null;

    const count = config.doorCount;
    const doors = [];
    const isSliding = config.doorType === 'sliding';
    const overlap = config.coupeGap ?? 26;
    const gap = config.doorGap ?? 2;

    let doorW, startXFunc, zIndexFunc;

    if (isSliding) {
      const innerW = config.width - 32;
      doorW = (innerW + (count - 1) * overlap) / count;
      startXFunc = (i: number) => 16 + i * (doorW - overlap);
      zIndexFunc = (i: number) => (i % 2 === 0 ? 40 : 41);
    } else {
      doorW = (config.width - (count + 1) * gap) / count;
      startXFunc = (i: number) => gap + i * (doorW + gap);
      zIndexFunc = () => 40;
    }

    const baseHeight = config.baseType === 'legs' ? 100 : (config.doorType === 'sliding' ? 70 : 100);
    const doorH = config.height - baseHeight - (isSliding ? 40 : gap);
    const doorY = baseHeight + (isSliding ? 0 : gap);

    for (let i = 0; i < count; i++) {
      doors.push(
        <div
          key={i}
          className="absolute border border-white/20 bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-[2px] flex items-center justify-center text-white/40 font-bold text-4xl select-none pointer-events-none transition-all hover:bg-white/10"
          style={{
            left: startXFunc(i) * scale,
            bottom: doorY * scale,
            width: doorW * scale,
            height: doorH * scale,
            zIndex: zIndexFunc(i),
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), inset 0 0 0 1px rgba(255, 255, 255, 0.1)',
          }}
        >
          <div className="absolute top-1/2 left-4 w-2 h-16 bg-white/20 rounded-full"></div>
          {i + 1}
        </div>
      );
    }
    return <div className="absolute inset-0 z-40 pointer-events-none">{doors}</div>;
  };

  const drawW = config.width * scale;
  const drawH = config.height * scale;
  const baseHeight = config.baseType === 'legs' ? 100 : (config.doorType === 'sliding' ? 70 : 100);

  return (
    <div
      ref={wrapperRef}
      className="flex-1 relative bg-[#151515] overflow-hidden flex items-center justify-center cursor-crosshair select-none group/canvas"
    >
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)`,
          backgroundSize: `${32 * scale}px ${32 * scale}px`,
        }}
      />

      <div className="absolute bottom-4 right-4 text-[10px] text-slate-600 font-mono">
        Масштаб: {(scale * 100).toFixed(0)}%
      </div>

      <div className="relative shadow-2xl transition-transform duration-75" style={{ width: drawW, height: drawH }}>
        {/* Dimensions (Outer) */}
        <div className="absolute -top-8 left-0 right-0 flex items-center justify-center pointer-events-none">
          <div className="h-px bg-slate-500 w-full absolute top-4"></div>
          <div className="h-2 w-px bg-slate-500 absolute top-3 left-0"></div>
          <div className="h-2 w-px bg-slate-500 absolute top-3 right-0"></div>
          <span className="bg-[#151515] px-2 text-xs font-bold text-slate-400 z-10">{config.width}</span>
        </div>
        <div className="absolute -left-10 top-0 bottom-0 flex flex-col items-center justify-center pointer-events-none h-full">
          <div className="w-px bg-slate-500 h-full absolute left-4"></div>
          <div className="w-2 h-px bg-slate-500 absolute left-3 top-0"></div>
          <div className="w-2 h-px bg-slate-500 absolute left-3 bottom-0"></div>
          <span className="bg-[#151515] py-2 px-1 text-xs font-bold text-slate-400 z-10 vertical-text">{config.height}</span>
        </div>

        {/* Cabinet Frame */}
        <div
          className="absolute inset-0 border-x-[16px] border-t-[16px] border-[#2d2d2d] bg-[#1e1e1e] box-border shadow-2xl"
          style={{
            borderLeftWidth: 16 * scale,
            borderRightWidth: 16 * scale,
            borderTopWidth: (config.construction === 'corpus' ? 16 : 0) * scale,
          }}
        />

        {/* Base / Plinth */}
        <div
          className="absolute left-0 right-0 bg-gradient-to-b from-[#2a2a2a] to-[#222] border-t border-white/5 flex items-center justify-center"
          style={{ bottom: 0, height: baseHeight * scale, zIndex: 5 }}
        >
          {config.baseType === 'legs' ? (
            <div className="flex gap-10 opacity-50">
              {[1, 2, 3].map(i => <div key={i} className="w-2 h-full bg-slate-500"></div>)}
            </div>
          ) : (
            <span className="text-[9px] text-slate-600 uppercase tracking-widest opacity-50">ЦОКОЛЬ {baseHeight}мм</span>
          )}
        </div>

        {/* Sections Container */}
        <div
          className="absolute inset-0 flex"
          style={{
            paddingLeft: 16 * scale,
            paddingRight: 16 * scale,
            paddingTop: (config.construction === 'corpus' ? 16 : 0) * scale,
            paddingBottom: baseHeight * scale,
          }}
        >
          {sections.map((sec, i) => {
            const sortedItems = [...sec.items].sort((a, b) => a.y - b.y);
            return (
              <React.Fragment key={sec.id}>
                <div
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectSection(i);
                  }}
                  className={`relative h-full transition-all border-r border-white/5 group/section ${
                    selectedSectionId === i ? 'bg-blue-900/10' : 'hover:bg-white/5'
                  }`}
                  style={{ width: sec.width * scale }}
                >
                  {/* Section Width Label */}
                  <div className="absolute top-2 w-full text-center text-[9px] text-slate-600 font-mono select-none opacity-0 group-hover/section:opacity-100 transition-opacity">
                    {Math.round(sec.width)}
                  </div>

                  {/* Items */}
                  {sec.items.map(item => (
                    <div
                      key={item.id}
                      onPointerDown={(e) => {
                        e.stopPropagation();
                        onSelectItem(item.id);
                        onSelectSection(i);
                        startDrag({
                          id: item.id,
                          startVal: item.y,
                          startMouseY: e.clientY,
                          startMouseX: e.clientX,
                          type: 'item',
                          offsetY: 0,
                        });
                      }}
                      className={`absolute left-0 right-0 cursor-move transition-all 
                        ${
                          selectedItemId === item.id
                            ? 'z-30 brightness-125 scale-[1.02]'
                            : 'z-20 brightness-100 hover:brightness-110'
                        }`}
                      style={{
                        bottom: (item.y - baseHeight) * scale,
                        height:
                          (item.type === 'drawer'
                            ? item.height
                            : item.type === 'rod'
                            ? 25
                            : item.type === 'partition'
                            ? item.height
                            : 16) * scale,
                      }}
                    >
                      <div
                        className="absolute inset-0 border border-white/30 bg-gradient-to-br from-white/20 to-white/10 backdrop-blur-sm flex items-center justify-center"
                        style={{
                          backgroundColor: `hsla(${i * 60}, 70%, 50%, 0.15)`,
                          borderColor: `hsla(${i * 60}, 70%, 50%, 0.5)`,
                        }}
                      >
                        <span className="text-[9px] font-bold text-slate-200 opacity-70">{item.name}</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Divider (between sections) */}
                {i < sections.length - 1 && (
                  <div
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      startDrag({
                        id: i,
                        startVal: sec.width,
                        startMouseY: e.clientY,
                        startMouseX: e.clientX,
                        type: 'divider',
                        offsetY: 0,
                      });
                    }}
                    className="relative cursor-col-resize hover:bg-blue-500/20 transition-colors"
                    style={{ width: 16 * scale, zIndex: 25 }}
                  >
                    <div className="absolute inset-y-0 left-1/2 w-1 bg-slate-500/20 -translate-x-1/2"></div>
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Snap Line Visual */}
        {snapLine !== null && (
          <div
            className="absolute left-0 right-0 border-t border-green-500 border-dashed z-50 pointer-events-none flex items-end justify-end pr-2 opacity-80"
            style={{ bottom: (snapLine - baseHeight) * scale, height: 1 }}
          >
            <span className="text-[9px] text-green-400 bg-black/90 px-1.5 py-0.5 rounded -translate-y-1/2 font-mono">
              ALIGN {Math.round(snapLine)}
            </span>
          </div>
        )}

        {/* Doors Overlay */}
        {renderDoors()}
      </div>
    </div>
  );
});

VisualEditor.displayName = 'VisualEditor';

export default VisualEditor;
