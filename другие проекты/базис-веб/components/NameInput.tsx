/**
 * NameInput Component - Validated name input field with real-time feedback
 * Phase 3: EditorPanel Refactoring
 */

import React from 'react';
import { InputValidator, ValidationResult } from '../services/InputValidator';

interface NameInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxLength?: number;
  validator?: InputValidator;
}

const validator = new InputValidator();

export const NameInput: React.FC<NameInputProps> = ({
  label,
  value,
  onChange,
  placeholder = '',
  maxLength = 100,
}) => {
  const [validationResult, setValidationResult] = React.useState<ValidationResult | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const textValue = e.target.value.slice(0, maxLength);
    
    // Validate
    const result = validator.validateInput(
      textValue,
      {
        type: 'string',
        required: true,
      },
      label
    );
    
    setValidationResult(result);
    onChange(textValue);
  };

  const hasError = validationResult && !validationResult.isValid;
  const charCount = value.length;

  return (
    <div>
      <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex justify-between">
        <span>{label}</span>
        <span className="text-slate-600">
          {charCount}/{maxLength}
        </span>
      </label>
      <input
        type="text"
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        className={`w-full mt-1.5 p-2 border rounded-md text-xs bg-slate-800 text-slate-100 focus:ring-2 outline-none transition ${
          hasError
            ? 'border-red-500 focus:ring-red-500'
            : 'border-slate-700 focus:ring-blue-500'
        }`}
      />
      {hasError && validationResult?.errors[0] && (
        <div className="mt-1 text-[10px] text-red-400">
          {validationResult.errors[0].message}
        </div>
      )}
    </div>
  );
};

export default NameInput;
