import React, { useCallback } from 'react';
import { Panel, Material } from '../../types';
import DimensionInput from '../DimensionInput';
import { inputValidator } from '../../services/InputValidator';
import { ScanLine, RotateCw } from 'lucide-react';
import { inputClass, labelClass } from './shared';

interface MainPropertiesTabProps {
  panel: Panel;
  materialLibrary: Material[];
  onUpdatePanel: (id: string, updates: Partial<Panel>) => void;
}

const MainPropertiesTab: React.FC<MainPropertiesTabProps> = ({
  panel,
  materialLibrary,
  onUpdatePanel,
}) => {
  const handleDimensionChange = useCallback(
    (field: 'width' | 'height', value: number) => {
      const result = inputValidator.validateInput(
        value,
        { type: 'number', min: 50, max: 5000 },
        field === 'width' ? 'Длина' : 'Ширина'
      );
      if (result.isValid && typeof result.sanitized === 'number') {
        onUpdatePanel(panel.id, { [field]: result.sanitized });
      }
    },
    [panel.id, onUpdatePanel]
  );

  const handlePositionChange = useCallback(
    (field: 'x' | 'y' | 'z', value: number) => {
      const min = field === 'z' ? -1000 : -5000;
      const max = field === 'z' ? 1000 : 5000;
      const label = field === 'x' ? 'X' : field === 'y' ? 'Y' : 'Z';
      const result = inputValidator.validateInput(
        value,
        { type: 'number', min, max },
        label
      );
      if (result.isValid && typeof result.sanitized === 'number') {
        onUpdatePanel(panel.id, { [field]: result.sanitized });
      }
    },
    [panel.id, onUpdatePanel]
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <DimensionInput
          label="Длина (L)"
          field="width"
          value={panel.width}
          onChange={(width) => handleDimensionChange('width', width)}
        />
        <DimensionInput
          label="Ширина (W)"
          field="height"
          value={panel.height}
          onChange={(height) => handleDimensionChange('height', height)}
        />
      </div>

      <div>
        <label className={labelClass}>Материал (ЛДСП)</label>
        <select
          value={panel.materialId}
          onChange={(e) => {
            const mat = materialLibrary.find((m) => m.id === e.target.value);
            if (mat)
              onUpdatePanel(panel.id, {
                materialId: mat.id,
                color: mat.color,
                texture: mat.texture,
                depth: mat.thickness,
              });
          }}
          className={inputClass}
        >
          {materialLibrary.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </div>

      <div
        className="flex items-center justify-between p-3 bg-slate-800 rounded border border-slate-700 cursor-pointer hover:border-slate-600 transition"
        onClick={() =>
          onUpdatePanel(panel.id, {
            textureRotation: panel.textureRotation === 0 ? 90 : 0,
          })
        }
      >
        <span className="text-[10px] font-bold text-slate-400 flex items-center gap-2">
          <ScanLine size={14} /> НАПРАВЛЕНИЕ ТЕКСТУРЫ
        </span>
        <div
          className={`flex items-center gap-2 text-xs px-3 py-1 rounded transition border ${
            panel.textureRotation === 90
              ? 'bg-blue-900/30 text-blue-400 border-blue-500/50'
              : 'bg-slate-700 text-slate-300 border-slate-600'
          }`}
        >
          <RotateCw
            size={14}
            className={panel.textureRotation === 90 ? 'rotate-90' : ''}
          />
          {panel.textureRotation}° (Вдоль {panel.textureRotation === 90 ? 'W' : 'L'})
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 border-t border-slate-800 pt-4">
        <DimensionInput
          label="X"
          field="x"
          value={Math.round(panel.x)}
          onChange={(x) => handlePositionChange('x', x)}
        />
        <DimensionInput
          label="Y"
          field="y"
          value={Math.round(panel.y)}
          onChange={(y) => handlePositionChange('y', y)}
        />
        <DimensionInput
          label="Z"
          field="z"
          value={Math.round(panel.z)}
          onChange={(z) => handlePositionChange('z', z)}
        />
      </div>
    </div>
  );
};

export default MainPropertiesTab;
