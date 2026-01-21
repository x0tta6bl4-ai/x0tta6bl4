---
description: Repository Information Overview
alwaysApply: true
---

# BazisLite-Web: Furniture CAD Application

## Summary

BazisLite-Web is a modern React-based web application for professional furniture and cabinet design with CAD operations. It enables users to design furniture pieces, optimize material cutting, create technical drawings, perform 2D nesting optimization, and manage production workflows. The application features dual 3D rendering engines (Three.js and Babylon.js), AI-assisted design through Google Gemini API, advanced cabinet configuration tools, hardware/fastener management, constraint solving, DFM validation, and FEA integration. Built as an AI Studio web app deployed on Vercel/similar platforms.

## Structure

**Root Level Entry Points**:
- `index.html` — Main HTML container with Tailwind CSS, ViewCube navigation styling, and responsive viewport setup
- `index.tsx` — React 19 DOM mount point with strict mode
- `App.tsx` — Core application orchestrator managing all view modes, state initialization, AI services, and project persistence

**Core Directories**:
- `components/` — React UI components for Scene3D, Scene3DBabylon, EditorPanel, CutList, DrawingView, NestingView, ProductionPipeline, CabinetWizard, AIAssistant, ParametricEditor, ProjectLibrary, TemplateSelector, ErrorBoundary, and specialized modules
- `services/` — Business logic layer including CabinetGenerator (furniture engine), geminiService (AI integration), hardwareUtils (fasteners/hinges), storageService (persistence), BillOfMaterials, ConstraintSolver, DFMValidator, FEAIntegration, CADExporter/Importer, HierarchyManager, InputValidator, and performance monitoring
- `store/` — Zustand state management (projectStore) for projects, panels, layers, and undo/redo history
- `workers/` — Web Workers for background processing (nesting.worker.js for 2D layout optimization)
- `hooks/` — Custom React hooks for performance metrics and utilities
- `types/` — TypeScript definitions (types.ts) for core data structures
- `cad/` — CAD-specific modules and utilities

**Configuration Files**:
- `vite.config.ts` — Vite build configuration with React plugin, dev server on port 3000
- `tsconfig.json` — TypeScript strict mode, ES2022 target, JSX support, path aliases
- `jest.config.js` — Jest testing with ts-jest transformer, node environment
- `materials.config.ts` — Pre-configured material library (Egger, Kronospan, Lamarty, MDF-RAL) with thicknesses 4-25mm
- `constants.ts` — Application constants and default values
- `.env.example` — Environment template for API keys

## Language & Runtime

**Language**: TypeScript 5.9.0 (strict mode)  
**React Version**: 19.2.3 (React DOM 19.2.3)  
**Target**: ES2022  
**Runtime**: Node.js 18+ (required)  
**Build System**: Vite 6.2.0  
**Package Manager**: npm  
**Module Type**: ES modules  
**Dev Server Port**: 3000 (host: 0.0.0.0)

## Dependencies

**Core UI & Graphics**:
- `react@19.2.3` — UI framework
- `react-dom@19.2.3` — DOM rendering
- `three@latest` — Primary 3D graphics engine
- `@babylonjs/core@6.32.1`, `@babylonjs/inspector@6.32.1`, `@babylonjs/loaders@6.32.1` — Alternative 3D rendering engine
- `lucide-react@latest` — Icon library
- `recharts@2.10.3` — Charts and analytics visualization

**State Management & AI**:
- `zustand@5.0.10` — Lightweight reactive state management
- `@google/generative-ai@latest` — Google Gemini API client for AI assistance
- `react-unity-webgl@9.4.2` — Unity WebGL integration

**Utilities**:
- `lodash@4.17.21` — Utility functions
- `numeric@1.2.6` — Numerical computation library
- `xml2js@0.4.23` — XML parsing and conversion
- `three-stl-loader@1.0.6` — STL file loader for 3D models

**Development**:
- `typescript@5.9.0` — TypeScript compiler
- `vite@6.2.0` — Build tool and dev server
- `@vitejs/plugin-react@5.0.0` — React plugin for Vite
- `jest@30.2.0` — Testing framework
- `ts-jest@29.4.6` — Jest TypeScript transformer
- `@types/*` — TypeScript definitions for node, three, jest

## Build & Installation

**Install Dependencies**:
```bash
npm install
```

**Development Server** (runs on http://localhost:3000):
```bash
npm run dev
```

**Production Build** (generates dist/ directory):
```bash
npm build
```

**Preview Production Build**:
```bash
npm run preview
```

**Type Checking**:
```bash
npm run typecheck
```

**Quick Start Scripts**:
- Windows: `start.bat` or PowerShell
- macOS/Linux: `./start.sh` (requires Node.js 18+)

**Environment Configuration**:
Create `.env.local`:
```
VITE_GEMINI_API_KEY=your_google_gemini_api_key
```

## Main Files & Resources

**Application Entry**: `index.tsx` — Mounts React app to DOM root element  
**Main Component**: `App.tsx` — Manages 13+ view modes (DESIGN, CUT_LIST, DRAWING, NESTING, PRODUCTION, WIZARD, SCRIPT, CAD_SOLVER, CAD_BOM, CAD_DFM, CAD_OPTIMIZATION, CAD_FEA, CAD_EXPORT), AI initialization, and project persistence  
**Type System**: `types.ts` — Defines Panel, Material, Hardware, CabinetConfig, Section, ProductionStage, and related structures  
**Materials Library**: `materials.config.ts` — Pre-configured materials with thickness, pricing, and texture specifications  
**Constants**: `constants.ts` — Default dimensions (1800×2500×650 mm), camera settings, validation constraints  
**State Management**: `store/projectStore.ts` — Zustand store for panels, layers, history, project metadata

**View Modes**:
- **Design** — 3D Cabinet configuration and visual parametric editing
- **Cut List** — Material breakdown and cutting optimization
- **Drawing** — Technical 2D drawings and assembly diagrams
- **Nesting** — 2D sheet layout optimization via Web Worker
- **Production Pipeline** — Workflow management with QR tracking
- **Cabinet Wizard** — Guided cabinet creation with presets
- **Script Editor** — Advanced parametric scripting
- **CAD Solver** — Constraint-based design optimization
- **CAD BOM** — Bill of materials and assembly hierarchy
- **CAD DFM** — Design for manufacturing validation
- **CAD Optimization** — Performance and cost optimization
- **CAD FEA** — Finite element analysis integration
- **CAD Export** — CAD file export/import (CADExporter, CADImporter services)

## Testing

**Framework**: Jest 30.2.0 with ts-jest transformer  
**Test Location**: `services/__tests__/` and inline `**/*.test.ts` files  
**Test Files**: 16 comprehensive test suites covering CabinetGenerator, ConstraintSolver, BillOfMaterials, DFMValidator, FEAIntegration, CADExporter/Importer, PerformanceMonitor, and assembly integration  
**Configuration**: `jest.config.js` — Node environment, path alias mapping, coverage from services/  
**Coverage**: Collected from `services/**/*.ts` (excluding tests)

**Run Tests**:
```bash
npm test                # Single run
npm run test:watch     # Watch mode
npm run test:coverage  # With coverage report
```

## Key Technical Features

**3D Visualization**: Dual-engine support (Three.js primary, Babylon.js alternative) with interactive ViewCube navigation and real-time feedback  
**AI Assistance**: Google Gemini integration for intelligent design suggestions via `geminiService.ts`  
**Constraint Solver**: Advanced `ConstraintSolver.ts` for parametric design validation  
**Cabinet Generation**: `CabinetGenerator.ts` (71 KB) — procedural furniture generation with hardware placement and optimization  
**Hardware Management**: `hardwareUtils.ts` for hinges, slides, dowels, shelf supports, fasteners  
**DFM Validation**: `DFMValidator.ts` for manufacturing feasibility checks  
**FEA Integration**: `FEAIntegration.ts` for structural analysis  
**Production Pipeline**: Full MES workflow with status tracking and QR codes  
**Data Persistence**: IndexedDB/localStorage via `storageService.ts` for auto-save  
**Performance Monitoring**: `PerformanceMonitor.ts` for metrics and optimization  
**Error Handling**: `ErrorBoundary.tsx` for graceful error recovery and user notifications
