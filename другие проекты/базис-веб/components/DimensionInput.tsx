/**
 * DimensionInput Component - Validated dimension input field
 * Phase 3: EditorPanel Refactoring
 */

import React from 'react';
import { InputValidator, ValidationResult } from '../services/InputValidator';

interface DimensionInputProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  field: 'width' | 'height' | 'depth' | 'x' | 'y' | 'z';
  validator?: InputValidator;
  showError?: boolean;
}

const validator = new InputValidator();

export const DimensionInput: React.FC<DimensionInputProps> = ({
  label,
  value,
  onChange,
  field,
  showError = true,
}) => {
  const [isFocused, setIsFocused] = React.useState(false);
  const [validationResult, setValidationResult] = React.useState<ValidationResult | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const numValue = parseFloat(e.target.value) || 0;
    
    // Validate on change
    const result = validator.validateInput(
      numValue,
      {
        type: 'number',
        min: field.includes('x') || field.includes('y') ? -5000 : field === 'z' ? -1000 : 50,
        max: field.includes('x') ? 5000 : field.includes('y') ? 5000 : field === 'z' ? 1000 : 5000,
      },
      label
    );
    
    setValidationResult(result);
    if (result.isValid) {
      onChange(numValue);
    }
  };

  const hasError = validationResult && !validationResult.isValid;

  return (
    <div>
      <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
        {label}
      </label>
      <input
        type="number"
        value={value}
        onChange={handleChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        className={`w-full mt-1.5 p-2 border rounded-md text-xs bg-slate-800 text-slate-100 focus:ring-2 outline-none transition font-mono ${
          hasError && showError
            ? 'border-red-500 focus:ring-red-500'
            : 'border-slate-700 focus:ring-blue-500'
        }`}
      />
      {hasError && showError && validationResult?.errors[0] && (
        <div className="mt-1 text-[10px] text-red-400">
          {validationResult.errors[0].message}
        </div>
      )}
    </div>
  );
};

export default DimensionInput;
