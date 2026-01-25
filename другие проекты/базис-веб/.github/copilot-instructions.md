# Copilot Instructions for Basis-Web CAD

## Project Overview
**базис-веб** is a parametric furniture CAD system built with React, TypeScript, and 3D visualization (Three.js/Babylon.js). It generates production-ready panel assemblies for cabinet manufacturing with constraint solving, BOM generation, and DFM validation.

**Tech Stack:** React 19, TypeScript, Zustand (state), Vite (build), Three.js/Babylon.js (3D), Jest/ts-jest (tests)

---

## Architecture Overview

### Core Data Model
- **Panel**: Basic 2D component (width, height, depth, material, edges, hardware, grooves)
- **Assembly**: Collection of panels with constraints and relationships
- **CabinetConfig**: Global dimensions (W/H/D), materials, styles
- **Section**: Vertical divisions in cabinet (shelf heights)
- **CabinetItem**: Individual items within sections (drawers, shelves, doors)

### State Management (Zustand)
- **projectStore** (`store/projectStore.ts`): Single source of truth for:
  - All panels with undo/redo history (max 50 steps)
  - Layers visibility/lock state
  - Production pipeline stage tracking
  - CAD solver outputs (Assembly, BOM, DFM, FEA)
  - Toast notifications
- History implemented via array with `historyIndex` pointer
- Actions use immutable patterns; avoid direct mutations

### Key Services Architecture

| Service | Responsibility | Key APIs |
|---------|---|---|
| **CabinetGenerator** | Generate panels from wizard config | `generate()`, `validate()`, `checkCollisions()` |
| **ConstraintSolver** | Resolve placement constraints | `solve()`, returns solved Assembly |
| **BillOfMaterials** | Aggregate components into BOM | `generate()`, handles nesting & quantities |
| **DFMValidator** | Check manufacturability (radii, holes, edges) | `validate()`, returns DFMReport |
| **CADExporter/Importer** | Format conversion (DXF, PDF, STL) | `export()`, `import()` |
| **geminiService** | Google Generative AI integration | `analyzeDesign()`, `generateVariations()` |
| **PerformanceMonitor** | FPS tracking, memory usage | `trackRender()`, `reportMetrics()` |

---

## Development Workflows

### Build & Run
```bash
npm run dev          # Start Vite dev server (http://localhost:3000)
npm run build        # Production build to dist/
npm run preview      # Preview production build
```

### Testing
```bash
npm test             # Run Jest (single pass)
npm run test:watch   # Watch mode for TDD
npm run test:coverage # Generate coverage report
npm run typecheck    # TypeScript type checking
```

### Environment Setup
- **`.env.local`** required: `VITE_GEMINI_API_KEY=your_key`
- API key NOT exported to client bundle (security enforced in vite.config.ts)
- Local AI service runs on `http://127.0.0.1:8001` (Python FastAPI)

---

## Project-Specific Conventions

### 1. Component Organization
- **UI Components** (`components/UI/`): Reusable primitives (NavigationBar, Toolbar, panels)
- **Feature Components** (`components/`): Feature-specific (CabinetWizard, Scene3D, ParametricEditor)
- **Hooks** (`hooks/`): State logic extraction (useCabinetWizardState, useSectionManagement)
- **Services** (`services/`): Business logic (algorithms, exports, integrations)

### 2. View Modes (Mutually Exclusive)
```typescript
enum ViewMode {
  WIZARD,      // Step-by-step cabinet builder
  DESIGN,      // Manual 2D panel editor
  PRODUCTION,  // Manufacturing pipeline
  NESTING,     // Cut optimization (Web Worker)
  DRAWING,     // 2D technical drawings
  CUT_LIST,    // Export panel specifications
}
```
Set via `setViewMode()` in App.tsx; only one active at a time.

### 3. Material Library Pattern
- Centralized in `materials.config.ts` (Material objects)
- Properties: article, brand, thickness, price, density, elasticModulus (for FEA)
- Referenced by `materialId` in panels; lookup via `MATERIAL_LIBRARY.find(m => m.id === materialId)`
- Constants (STD = standard dimensions) in CabinetGenerator.ts

### 4. Validation Strategy
- Input validation: `InputValidator.ts` (dimensions, collisions, constraints)
- Cabinet generation validates before returning: check `validation.valid` before use
- Error messages in Russian; collect in array, display via error boundary or toast

### 5. Production Pipeline
- **Stages**: design → cutting → edging → drilling → assembly → quality_control → shipping
- **Per-panel status**: pending, in_progress, completed
- Global stage in store; UI tracks both
- **DFM validation** runs before advancing stage to catch manufacturability issues early

---

## Bundle Optimization (Critical)
- **Dynamic imports** for heavy 3D libraries to reduce initial load (~87% reduction achieved)
- Scene3D (Three.js ~592 KB) and Scene3DBabylon (Babylon.js ~3.8 MB) use lazy imports + Suspense
- NestingView loaded on-demand; includes Web Worker for guillotine algorithm
- Main bundle now ~372 KB

**Pattern:**
```typescript
// App.tsx
const Scene3D = React.lazy(() => import('./components/Scene3D'));

// Usage
<Suspense fallback={<LoadingSpinner />}>
  <Scene3D engine="three" />
</Suspense>
```

---

## Common Patterns & Anti-Patterns

### ✅ DO:
1. **Use Zustand selectors** to minimize re-renders:
   ```typescript
   const panels = useProjectStore(s => s.panels);  // only re-render if panels change
   ```
2. **Validate early** in CabinetGenerator before expensive geometry ops
3. **Cache Material lookups** in ParameterCache for repeated access
4. **Store computed values** in state if used multiple renders
5. **Test service logic independently** before component integration

### ❌ DON'T:
1. Mutate Panel objects directly; use `updatePanel(id, { field: newValue })`
2. Import Scene3D statically; always use lazy + Suspense for 3D components
3. Call `pushHistory()` for every state change; batch them
4. Hardcode material constants; reference from `materials.config.ts`
5. Expose API keys to client bundles

---

## Cross-Component Communication

### Data Flow
1. **User Action** → Component event handler
2. **Update Store** → Zustand action (e.g., `updatePanel`)
3. **Store notifies subscribers** → Components re-render with selector hooks
4. **Service called if needed** → CabinetGenerator, BillOfMaterials, etc.
5. **Results back to Store** → `setSolvedAssembly()`, `setBOMData()`, etc.

### Example: Cabinet Generation
```typescript
// CabinetWizard.tsx
const onGenerate = () => {
  const generator = new CabinetGenerator(config, sections, materials);
  const validation = generator.validate();
  if (validation.valid) {
    const panels = generator.generate();
    useProjectStore.getState().setPanels(panels);  // persist & notify all subscribers
  }
};
```

---

## Key Files for Reference

| Path | Purpose |
|------|---------|
| [App.tsx](../App.tsx) | Main app structure, view mode routing, initialization |
| [constants.ts](../constants.ts) | All magic numbers (camera, defaults, thresholds) |
| [store/projectStore.ts](../store/projectStore.ts) | Central state + history implementation |
| [types.ts](../types.ts) | Core data structures (Panel, Material, Hardware) |
| [materials.config.ts](../materials.config.ts) | Material library (brands, properties, pricing) |
| [services/CabinetGenerator.ts](../services/CabinetGenerator.ts) | Panel generation algorithm (1440 lines) |
| [services/ConstraintSolver.ts](../services/ConstraintSolver.ts) | Assembly constraint resolution |
| [vite.config.ts](../vite.config.ts) | Build config + security (API key isolation) |
| [jest.config.js](../jest.config.js) | Test runner config (ts-jest preset) |

---

## Testing Guidelines

- **Unit tests** in `services/__tests__/` for algorithms (CabinetGenerator, ConstraintSolver, validators)
- **Mock heavy dependencies** (materials, geometry calculations) in tests
- **Integration tests** verify store + service interaction
- **Coverage target**: 80% on critical paths (generation, export, validation)
- **Avoid mocking**: Real Material library for realistic tests

---

## Performance Considerations

1. **Render Optimization**: Use `React.memo()` for expensive components, selector hooks to prevent prop changes
2. **Geometry Caching**: LRU cache for computed mesh geometries; invalidate on material change
3. **LOD (Level of Detail)**: Scene3D renders simplified geometry for >1000 panels
4. **Web Workers**: NestingView uses worker pool for guillotine algorithm (non-blocking)
5. **Memory**: Monitor with `PerformanceMonitor.ts`; target 60 FPS at 1000+ panels

---

## Debugging Tips

- **Check Zustand state**: `useProjectStore.getState()` in console
- **View history**: `getState().history` and `historyIndex`
- **Material lookup issues**: Verify `materialId` exists in config, not just assumed
- **Performance**: Use `PerformanceMonitor.trackRender()` to identify bottlenecks
- **3D camera stuck?** Check `CAMERA_CONFIG` in constants.ts; reset via `setShow3DView(false) → true`

---

## Documentation Index

For deeper understanding, refer to workspace docs:
- **WEB_CAD_RESEARCH_SUMMARY.md** - Architecture overview
- **ARCHITECTURE_BEST_PRACTICES.md** - Design patterns (Command, Observer, Factory)
- **IMPLEMENTATION_MVP_5DAYS.md** - Step-by-step implementation guide
- **CAD_IMPLEMENTATION_PLAN_18WEEKS.md** - Full feature roadmap

---

## Next Steps for New Agents

1. Read this file (3 min)
2. Skim [constants.ts](../constants.ts) to understand configuration (5 min)
3. Review [types.ts](../types.ts) for data models (5 min)
4. Examine one feature end-to-end (e.g., CabinetWizard) to see patterns in action (10 min)
5. Start implementing with confidence!
