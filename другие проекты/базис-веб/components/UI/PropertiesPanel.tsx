import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Panel, Axis, TextureType, EdgeThickness } from '../../types';
import ValidationPanel from '../ValidationPanel';
import { useProjectStore } from '../../store/projectStore';

interface PropertiesPanelProps {
  selectedPanel: Panel | null;
  onPanelUpdate: (id: string, changes: Partial<Panel>) => void;
  materials: any[];
}

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({ title, defaultOpen = true, children }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-slate-700">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/50 transition-colors text-slate-300 font-semibold text-sm"
      >
        {title}
        {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {isOpen && <div className="px-4 py-3 space-y-3 bg-slate-800/50 border-t border-slate-700">{children}</div>}
    </div>
  );
};

interface FormFieldProps {
  label: string;
  value: string | number;
  onChange: (value: string | number) => void;
  type?: 'text' | 'number' | 'select' | 'color';
  options?: { label: string; value: any }[];
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
}

const FormField: React.FC<FormFieldProps> = ({
  label,
  value,
  onChange,
  type = 'text',
  options = [],
  unit = '',
  min,
  max,
  step
}) => {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{label}</label>

      {type === 'text' && (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="bg-slate-700 text-slate-100 rounded px-2 py-1.5 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none transition-colors"
        />
      )}

      {type === 'number' && (
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={value}
            onChange={(e) => onChange(parseFloat(e.target.value))}
            min={min}
            max={max}
            step={step}
            className="flex-1 bg-slate-700 text-slate-100 rounded px-2 py-1.5 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none transition-colors"
          />
          {unit && <span className="text-xs text-slate-400 w-8">{unit}</span>}
        </div>
      )}

      {type === 'color' && (
        <div className="flex items-center gap-2">
          <input
            type="color"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="w-12 h-8 rounded cursor-pointer border border-slate-600"
          />
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="flex-1 bg-slate-700 text-slate-100 rounded px-2 py-1.5 text-sm border border-slate-600 focus:border-blue-500 font-mono"
          />
        </div>
      )}

      {type === 'select' && (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="bg-slate-700 text-slate-100 rounded px-2 py-1.5 text-sm border border-slate-600 focus:border-blue-500 focus:outline-none transition-colors cursor-pointer"
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )}
    </div>
  );
};

export const PropertiesPanel: React.FC<PropertiesPanelProps> = ({
  selectedPanel,
  onPanelUpdate,
  materials
}) => {
  if (!selectedPanel) {
    return (
      <div className="w-80 bg-slate-900 border-l border-slate-700 flex flex-col h-full">
        <div className="bg-slate-800 px-4 py-3 border-b border-slate-700">
          <h2 className="text-white font-semibold text-sm">Свойства</h2>
        </div>
        <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
          Выберите объект для редактирования
        </div>
      </div>
    );
  }

  const updatePanel = (changes: Partial<Panel>) => {
    onPanelUpdate(selectedPanel.id, changes);
  };

  return (
    <div className="w-80 bg-slate-900 border-l border-slate-700 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="bg-slate-800 px-4 py-3 border-b border-slate-700 flex-shrink-0">
        <h2 className="text-white font-semibold text-sm truncate">{selectedPanel.name}</h2>
        <p className="text-xs text-slate-400 mt-1">ID: {selectedPanel.id}</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Dimensions */}
        <CollapsibleSection title="Размеры" defaultOpen={true}>
          <FormField
            label="Ширина"
            value={selectedPanel.width}
            onChange={(v) => updatePanel({ width: Number(v) })}
            type="number"
            unit="мм"
            min={10}
            step={1}
          />
          <FormField
            label="Высота"
            value={selectedPanel.height}
            onChange={(v) => updatePanel({ height: Number(v) })}
            type="number"
            unit="мм"
            min={10}
            step={1}
          />
          <FormField
            label="Толщина"
            value={selectedPanel.depth}
            onChange={(v) => updatePanel({ depth: Number(v) })}
            type="number"
            unit="мм"
            min={1}
            step={0.1}
          />
        </CollapsibleSection>

        {/* Position */}
        <CollapsibleSection title="Позиция">
          <FormField
            label="X"
            value={selectedPanel.x}
            onChange={(v) => updatePanel({ x: Number(v) })}
            type="number"
            unit="мм"
            step={1}
          />
          <FormField
            label="Y"
            value={selectedPanel.y}
            onChange={(v) => updatePanel({ y: Number(v) })}
            type="number"
            unit="мм"
            step={1}
          />
          <FormField
            label="Z"
            value={selectedPanel.z}
            onChange={(v) => updatePanel({ z: Number(v) })}
            type="number"
            unit="мм"
            step={1}
          />
        </CollapsibleSection>

        {/* Rotation */}
        <CollapsibleSection title="Ориентация">
          <FormField
            label="Ось вращения"
            value={selectedPanel.rotation}
            onChange={(v) => updatePanel({ rotation: v as Axis })}
            type="select"
            options={[
              { label: 'По оси X', value: Axis.X },
              { label: 'По оси Y', value: Axis.Y },
              { label: 'По оси Z', value: Axis.Z }
            ]}
          />
        </CollapsibleSection>

        {/* Material */}
        <CollapsibleSection title="Материал">
          <FormField
            label="Материал"
            value={selectedPanel.materialId}
            onChange={(v) => updatePanel({ materialId: v as string })}
            type="select"
            options={materials.map((m) => ({ label: m.name, value: m.id }))}
          />
          <FormField
            label="Цвет"
            value={selectedPanel.color}
            onChange={(v) => updatePanel({ color: v as string })}
            type="color"
          />
        </CollapsibleSection>

        {/* Texture */}
        <CollapsibleSection title="Текстура">
          <FormField
            label="Тип текстуры"
            value={selectedPanel.texture}
            onChange={(v) => updatePanel({ texture: v as TextureType })}
            type="select"
            options={[
              { label: 'Нет', value: TextureType.NONE },
              { label: 'Дерево (Дуб)', value: TextureType.WOOD_OAK },
              { label: 'Дерево (Орех)', value: TextureType.WOOD_WALNUT },
              { label: 'Дерево (Ясень)', value: TextureType.WOOD_ASH },
              { label: 'Бетон', value: TextureType.CONCRETE },
              { label: 'Однородный', value: TextureType.UNIFORM }
            ]}
          />
          <FormField
            label="Поворот"
            value={selectedPanel.textureRotation}
            onChange={(v) => updatePanel({ textureRotation: Number(v) as any })}
            type="number"
            unit="°"
            min={0}
            max={360}
            step={15}
          />
        </CollapsibleSection>

        {/* Edging */}
        <CollapsibleSection title="Кромкование">
          <div className="space-y-2">
            {(['top', 'bottom', 'left', 'right'] as const).map((side) => (
              <FormField
                key={side}
                label={
                  side === 'top'
                    ? 'Верхняя'
                    : side === 'bottom'
                      ? 'Нижняя'
                      : side === 'left'
                        ? 'Левая'
                        : 'Правая'
                }
                value={selectedPanel.edging[side]}
                onChange={(v) =>
                  updatePanel({
                    edging: {
                      ...selectedPanel.edging,
                      [side]: v as EdgeThickness
                    }
                  })
                }
                type="select"
                options={[
                  { label: 'Нет', value: 'none' },
                  { label: '0.4 мм', value: '0.4' },
                  { label: '1.0 мм', value: '1.0' },
                  { label: '2.0 мм', value: '2.0' }
                ]}
              />
            ))}
          </div>
        </CollapsibleSection>

        {/* Visibility */}
        <CollapsibleSection title="Видимость">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selectedPanel.visible}
              onChange={(e) => updatePanel({ visible: e.target.checked })}
              className="w-4 h-4 rounded border border-slate-600 cursor-pointer"
            />
            <label className="text-sm text-slate-300 cursor-pointer">Видимо</label>
          </div>
        </CollapsibleSection>

        {/* Validation Results */}
        <CollapsibleSection title="🔍 Результаты валидации" defaultOpen={false}>
          <ValidationPanel panels={[selectedPanel]} />
        </CollapsibleSection>
      </div>
    </div>
  );
};
