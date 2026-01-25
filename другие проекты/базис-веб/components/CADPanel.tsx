import React, { useState, useEffect } from 'react';
import { useProjectStore } from '../store/projectStore';
import { CADEngine, useCADStore } from '../services/cad';
import { Constraint } from '../services/cad/CADTypes';

const CONSTRAINT_TYPES = ['distance', 'angle', 'parallel', 'perpendicular', 'coincident', 'equal', 'horizontal', 'vertical'] as const;

/**
 * CADPanel - Professional CAD interface component
 * 
 * Provides:
 * - Parameter management (create, modify constraints)
 * - Real-time constraint solving
 * - Manufacturing validation
 * - Design history (undo/redo)
 * - Statistics and performance monitoring
 */
export const CADPanel: React.FC = () => {
  // CAD Store hooks
  const {
    createModel,
    getActiveModel,
    createParameter,
    updateParameter,
    addConstraint,
    validateModel,
    solveConstraints,
    undoAction,
    redoAction,
    getStats,
  } = useCADStore();

  // Project Store for panel generation
  const { setPanels } = useProjectStore();

  // UI State
  const [activeTab, setActiveTab] = useState<'parameters' | 'constraints' | 'validation' | 'history'>('parameters');
  const [modelName, setModelName] = useState('Cabinet');
  const [showStats, setShowStats] = useState(false);
  const [selectedParameterId, setSelectedParameterId] = useState<string | null>(null);

  // Parameter form state
  const [paramName, setParamName] = useState('');
  const [paramValue, setParamValue] = useState(100);
  const [paramMin, setParamMin] = useState(50);
  const [paramMax, setParamMax] = useState(500);
  const [paramUnit, setParamUnit] = useState('mm');

  // Constraint form state
  const [constraintType, setConstraintType] = useState<ConstraintType>(ConstraintType.DISTANCE);
  const [constraintValue, setConstraintValue] = useState(100);
  const [elementA, setElementA] = useState('');
  const [elementB, setElementB] = useState('');

  const model = getActiveModel();

  // Initialize model on mount
  useEffect(() => {
    if (!model) {
      createModel(modelName, 'CAD Professional Design');
    }
  }, []);

  const handleCreateParameter = () => {
    if (!model || !paramName.trim()) return;

    try {
      createParameter(model.id, paramName, paramValue, {
        min: paramMin,
        max: paramMax,
        unit: paramUnit,
      });

      // Reset form
      setParamName('');
      setParamValue(100);
      setParamMin(50);
      setParamMax(500);
    } catch (err) {
      console.error('Failed to create parameter:', err);
    }
  };

  const handleUpdateParameter = (paramId: string, value: number) => {
    if (!model) return;

    try {
      updateParameter(model.id, paramId, value);
    } catch (err) {
      console.error('Failed to update parameter:', err);
    }
  };

  const handleAddConstraint = () => {
    if (!model || !elementA || !elementB) return;

    try {
      addConstraint(model.id, constraintType, [{ id: elementA }, { id: elementB }], constraintValue);
      setElementA('');
      setElementB('');
      setConstraintValue(100);
    } catch (err) {
      console.error('Failed to add constraint:', err);
    }
  };

  const handleValidate = () => {
    if (!model) return;

    try {
      const result = validateModel();
      console.log('Validation result:', result);
      // Show validation modal or toast
    } catch (err) {
      console.error('Validation failed:', err);
    }
  };

  const handleSolve = () => {
    if (!model) return;

    try {
      const result = solveConstraints();
      console.log('Solver result:', result);
      // Show solver feedback
    } catch (err) {
      console.error('Solving failed:', err);
    }
  };

  const handleExportPanels = () => {
    if (!model || !model.bodies.length) {
      alert('No bodies in model. Create parameters and constraints first.');
      return;
    }

    // Convert CAD bodies to panels for visualization
    const panels = model.bodies.map((body, idx) => ({
      id: `cad-${body.id}`,
      name: `Body ${idx + 1}`,
      x: body.aabb.center.x,
      y: body.aabb.center.y,
      z: body.aabb.center.z,
      width: body.aabb.size.x,
      height: body.aabb.size.y,
      depth: body.aabb.size.z,
      materialId: 'eg-w980',
      color: '#D2B48C',
      visible: true,
      layer: 'body',
      rotation: 'Z' as const,
      texture: 'none' as const,
      textureRotation: 0 as const,
      openingType: 'none' as const,
      edging: { top: 'none', bottom: 'none', left: 'none', right: 'none' } as const,
      groove: { enabled: false, side: 'top' as const, width: 0, depth: 0, offset: 0 },
      hardware: [],
      productionStatus: 'pending' as const,
      currentStage: 'design' as const,
    }));

    setPanels(panels);
    alert(`Exported ${panels.length} bodies to main design view`);
  };

  const stats = model ? getStats() : null;

  return (
    <div className="w-full h-full bg-slate-900 text-slate-100 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="bg-slate-800 border-b border-slate-700 p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-bold">CAD Professional Engine</h2>
          <div className="flex gap-2">
            <button
              onClick={() => undoAction()}
              className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs font-semibold"
              title="Undo (Ctrl+Z)"
            >
              ↶ Undo
            </button>
            <button
              onClick={() => redoAction()}
              className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs font-semibold"
              title="Redo (Ctrl+Y)"
            >
              ↷ Redo
            </button>
            <button
              onClick={() => setShowStats(!showStats)}
              className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-xs font-semibold"
            >
              {showStats ? 'Hide' : 'Show'} Stats
            </button>
          </div>
        </div>

        {/* Model Info */}
        <div className="text-xs text-slate-400">
          <span className="font-semibold">Model:</span> {model?.name || 'None loaded'}
          {stats && (
            <>
              <span className="ml-4">
                <span className="font-semibold">Parameters:</span> {stats.parameterCount}
              </span>
              <span className="ml-4">
                <span className="font-semibold">Constraints:</span> {stats.constraintCount}
              </span>
              <span className="ml-4">
                <span className="font-semibold">Solver:</span> {stats.lastSolveConverged ? '✓ Converged' : '✗ Failed'}
              </span>
            </>
          )}
        </div>

        {/* Stats Panel */}
        {showStats && stats && (
          <div className="mt-3 p-3 bg-slate-700 rounded text-xs grid grid-cols-3 gap-4">
            <div>
              <div className="text-slate-400">Bodies</div>
              <div className="text-xl font-bold text-blue-400">{stats.bodyCount}</div>
            </div>
            <div>
              <div className="text-slate-400">Total Volume</div>
              <div className="text-xl font-bold text-green-400">{(stats.totalVolume || 0).toFixed(0)} mm³</div>
            </div>
            <div>
              <div className="text-slate-400">Last Solve Time</div>
              <div className="text-xl font-bold text-purple-400">{(stats.lastSolveTime || 0).toFixed(1)} ms</div>
            </div>
          </div>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-0 border-b border-slate-700 bg-slate-800">
        {(['parameters', 'constraints', 'validation', 'history'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${
              activeTab === tab
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-300'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Parameters Tab */}
        {activeTab === 'parameters' && (
          <div className="space-y-4">
            <div className="bg-slate-800 p-4 rounded border border-slate-700">
              <h3 className="font-bold mb-3 text-sm">Create Parameter</h3>
              <div className="space-y-2">
                <input
                  type="text"
                  placeholder="Parameter name (e.g., 'Width')"
                  value={paramName}
                  onChange={(e) => setParamName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-xs text-slate-100 placeholder-slate-500"
                />
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    placeholder="Value"
                    value={paramValue}
                    onChange={(e) => setParamValue(parseFloat(e.target.value))}
                    className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-xs text-slate-100"
                  />
                  <input
                    type="number"
                    placeholder="Min"
                    value={paramMin}
                    onChange={(e) => setParamMin(parseFloat(e.target.value))}
                    className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-xs text-slate-100"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    placeholder="Max"
                    value={paramMax}
                    onChange={(e) => setParamMax(parseFloat(e.target.value))}
                    className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-xs text-slate-100"
                  />
                  <select
                    value={paramUnit}
                    onChange={(e) => setParamUnit(e.target.value)}
                    className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-xs text-slate-100"
                  >
                    <option>mm</option>
                    <option>cm</option>
                    <option>m</option>
                    <option>inch</option>
                  </select>
                </div>
                <button
                  onClick={handleCreateParameter}
                  className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-500 rounded text-xs font-bold text-white transition"
                >
                  Create Parameter
                </button>
              </div>
            </div>

            {/* Parameters List */}
            <div className="bg-slate-800 p-4 rounded border border-slate-700">
              <h3 className="font-bold mb-3 text-sm">Parameters</h3>
              {model && model.parameters.length > 0 ? (
                <div className="space-y-2">
                  {model.parameters.map((param) => (
                    <div key={param.id} className="flex items-center gap-2 p-2 bg-slate-700 rounded">
                      <div className="flex-1">
                        <div className="text-xs font-semibold text-blue-300">{param.name}</div>
                        <div className="text-xs text-slate-400">
                          {param.value.toFixed(2)} {param.unit}
                        </div>
                        <input
                          type="range"
                          min={param.min}
                          max={param.max}
                          value={param.value}
                          onChange={(e) => handleUpdateParameter(param.id, parseFloat(e.target.value))}
                          className="w-full mt-1 h-1 bg-slate-600 rounded"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic">No parameters created yet</p>
              )}
            </div>
          </div>
        )}

        {/* Constraints Tab */}
        {activeTab === 'constraints' && (
          <div className="space-y-4">
            <div className="bg-slate-800 p-4 rounded border border-slate-700">
              <h3 className="font-bold mb-3 text-sm">Add Constraint</h3>
              <div className="space-y-2">
                <select
                  value={constraintType}
                  onChange={(e) => setConstraintType(e.target.value as ConstraintType)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-xs text-slate-100"
                >
                  <option value={ConstraintType.DISTANCE}>Distance</option>
                  <option value={ConstraintType.ANGLE}>Angle</option>
                  <option value={ConstraintType.PARALLEL}>Parallel</option>
                  <option value={ConstraintType.PERPENDICULAR}>Perpendicular</option>
                  <option value={ConstraintType.COINCIDENT}>Coincident</option>
                  <option value={ConstraintType.EQUAL}>Equal</option>
                  <option value={ConstraintType.HORIZONTAL}>Horizontal</option>
                  <option value={ConstraintType.VERTICAL}>Vertical</option>
                </select>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    placeholder="Element A ID"
                    value={elementA}
                    onChange={(e) => setElementA(e.target.value)}
                    className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-xs text-slate-100 placeholder-slate-500"
                  />
                  <input
                    type="text"
                    placeholder="Element B ID"
                    value={elementB}
                    onChange={(e) => setElementB(e.target.value)}
                    className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-xs text-slate-100 placeholder-slate-500"
                  />
                </div>
                <input
                  type="number"
                  placeholder="Constraint value"
                  value={constraintValue}
                  onChange={(e) => setConstraintValue(parseFloat(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-xs text-slate-100"
                />
                <button
                  onClick={handleAddConstraint}
                  className="w-full px-3 py-2 bg-green-600 hover:bg-green-500 rounded text-xs font-bold text-white transition"
                >
                  Add Constraint
                </button>
              </div>
            </div>

            {/* Constraints List */}
            <div className="bg-slate-800 p-4 rounded border border-slate-700">
              <h3 className="font-bold mb-3 text-sm">Active Constraints</h3>
              {model && model.constraints.length > 0 ? (
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {model.constraints.map((constraint) => (
                    <div key={constraint.id} className="text-xs p-2 bg-slate-700 rounded font-mono">
                      <div className="text-green-400">{constraint.type}</div>
                      <div className="text-slate-400">
                        {constraint.elementA} → {constraint.elementB} = {constraint.value}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic">No constraints added yet</p>
              )}
            </div>
          </div>
        )}

        {/* Validation Tab */}
        {activeTab === 'validation' && (
          <div className="space-y-4">
            <div className="flex gap-2">
              <button
                onClick={handleValidate}
                className="flex-1 px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded text-sm font-bold text-white transition"
              >
                Validate Model
              </button>
              <button
                onClick={handleSolve}
                className="flex-1 px-4 py-2 bg-orange-600 hover:bg-orange-500 rounded text-sm font-bold text-white transition"
              >
                Solve Constraints
              </button>
            </div>

            <div className="bg-slate-800 p-4 rounded border border-slate-700">
              <h3 className="font-bold mb-3 text-sm">Validation Issues</h3>
              <p className="text-xs text-slate-400 italic">Run validation to check for issues</p>
            </div>

            <div className="bg-slate-800 p-4 rounded border border-slate-700">
              <h3 className="font-bold mb-3 text-sm">Export to Design View</h3>
              <button
                onClick={handleExportPanels}
                className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm font-bold text-white transition"
              >
                Export CAD Bodies as Panels
              </button>
              <p className="text-xs text-slate-400 mt-2">
                Converts CAD bodies to panels for 3D visualization in main design view
              </p>
            </div>
          </div>
        )}

        {/* History Tab */}
        {activeTab === 'history' && (
          <div className="bg-slate-800 p-4 rounded border border-slate-700">
            <h3 className="font-bold mb-3 text-sm">History</h3>
            <p className="text-xs text-slate-400 italic">History tracking not yet implemented in UI</p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => undoAction()}
                className="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded text-xs font-bold"
              >
                ↶ Undo
              </button>
              <button
                onClick={() => redoAction()}
                className="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded text-xs font-bold"
              >
                ↷ Redo
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CADPanel;
