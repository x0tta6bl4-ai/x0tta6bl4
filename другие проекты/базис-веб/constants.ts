/**
 * Application Configuration Constants
 * 
 * Centralized configuration for all magic numbers and default values
 * Update here instead of searching through the codebase
 */

// ============================================================================
// DEFAULT PROJECT CONFIGURATION
// ============================================================================

export const DEFAULT_CABINET_CONFIG = {
  /** Default cabinet width (mm) */
  WIDTH: 1800,
  
  /** Default cabinet height (mm) */
  HEIGHT: 2500,
  
  /** Default cabinet depth (mm) */
  DEPTH: 650,
  
  /** Default material ID */
  MATERIAL_ID: 'eg-w980',
  
  /** Default material thickness (mm) */
  MATERIAL_THICKNESS: 16,
} as const;

// ============================================================================
// CAMERA & VIEWPORT CONFIGURATION
// ============================================================================

export const CAMERA_CONFIG = {
  /** Initial camera X position (units) */
  INITIAL_X: 2000,
  
  /** Initial camera Y position (units) */
  INITIAL_Y: 1500,
  
  /** Initial camera Z position (units) */
  INITIAL_Z: 2500,
  
  /** Camera angular sensitivity (lower = faster) */
  ANGULAR_SENSIBILITY: 1000,
  
  /** Camera inertia (0-1, higher = more inertia) */
  INERTIA: 0.7,
  
  /** Camera movement speed (units per second) */
  SPEED: 50,
} as const;

// ============================================================================
// LIGHTING CONFIGURATION
// ============================================================================

export const LIGHTING_CONFIG = {
  /** Hemispheric light intensity (0-1) */
  HEMISPHERIC_INTENSITY: 0.7,
  
  /** Hemispheric light ground color (RGB 0-1) */
  GROUND_COLOR_RGB: [0.267, 0.267, 0.267] as const,
  
  /** Point light intensity (0-1) */
  POINT_INTENSITY: 0.8,
  
  /** Point light range (units) */
  POINT_RANGE: 50000,
  
  /** Point light position (X, Y, Z) */
  POINT_LIGHT_POSITION: [1500, 3000, 1500] as const,
} as const;

// ============================================================================
// GRID & AXES CONFIGURATION
// ============================================================================

export const GRID_CONFIG = {
  /** Grid size (mm) */
  SIZE: 10000,
  
  /** Grid subdivisions */
  SUBDIVISIONS: 100,
  
  /** Grid Y offset (below cabinet) */
  Y_OFFSET: -1,
  
  /** Grid base color (RGB 0-1) */
  COLOR_RGB: [0.2, 0.2, 0.2] as const,
  
  /** Grid emissive color (RGB 0-1) */
  EMISSIVE_RGB: [0.15, 0.15, 0.15] as const,
} as const;

// ============================================================================
// SCENE RENDERING CONFIGURATION
// ============================================================================

export const SCENE_CONFIG = {
  /** Scene background color (RGBA 0-1) */
  CLEAR_COLOR: [0.1, 0.1, 0.1, 1.0] as const,
  
  /** Enable collisions */
  COLLISIONS_ENABLED: true,
  
  /** Preserve drawing buffer (for screenshots) */
  PRESERVE_DRAWING_BUFFER: true,
  
  /** Enable stencil buffer */
  STENCIL_ENABLED: true,
  
  /** Enable antialiasing */
  ANTIALIAS_ENABLED: true,
} as const;

// ============================================================================
// PANEL CONSTRAINTS (VALIDATION)
// ============================================================================

export const PANEL_CONSTRAINTS = {
  // Width constraints (mm)
  WIDTH_MIN: 50,
  WIDTH_MAX: 5000,
  
  // Height constraints (mm)
  HEIGHT_MIN: 50,
  HEIGHT_MAX: 5000,
  
  // Depth constraints (mm)
  DEPTH_MIN: 50,
  DEPTH_MAX: 2000,
  
  // Position constraints
  POSITION_MIN: -10000,
  POSITION_MAX: 10000,
  
  // Thickness constraints (mm)
  THICKNESS_MIN: 8,
  THICKNESS_MAX: 50,
} as const;

// ============================================================================
// DRAWER CONFIGURATION
// ============================================================================

export const DRAWER_CONFIG = {
  /** Standard drawer height (mm) */
  STANDARD_HEIGHT: 176,
  
  /** Minimum drawer depth (mm) */
  MIN_DEPTH: 300,
  
  /** Minimum clearance from cabinet back (mm) */
  MIN_CLEARANCE: 10,
} as const;

// ============================================================================
// HINGE CONFIGURATION (FURNITURE STANDARDS)
// ============================================================================

export const HINGE_CONFIG = {
  /** Hinge count thresholds by cabinet height (mm) */
  HEIGHT_1: { threshold: 900, hinges: 2 },
  HEIGHT_2: { threshold: 1600, hinges: 3 },
  HEIGHT_3: { threshold: 2000, hinges: 4 },
  HEIGHT_4: { threshold: Infinity, hinges: 5 },
  
  /** Standard hinge cup diameter (mm) */
  CUP_DIAMETER: 35,
  
  /** Standard hinge distance from edge (mm) */
  EDGE_DISTANCE: 50,
} as const;

// ============================================================================
// SHELF DEFLECTION LIMITS (FURNITURE STANDARDS)
// ============================================================================

export const SHELF_DEFLECTION = {
  /** Maximum span for light load (mm) */
  LIGHT_LOAD_MAX_SPAN: 700,
  
  /** Maximum span for heavy load (mm) */
  HEAVY_LOAD_MAX_SPAN: 550,
  
  /** Critical error threshold (mm) */
  CRITICAL_SPAN: 800,
  
  /** Material thickness for calculations (mm) */
  PARTICLE_BOARD_THICKNESS: 16,
} as const;

// ============================================================================
// AUTO-SAVE CONFIGURATION
// ============================================================================

export const AUTO_SAVE_CONFIG = {
  /** Auto-save interval (milliseconds) */
  INTERVAL_MS: 30000, // 30 seconds
  
  /** Local storage key for project data */
  STORAGE_KEY: 'bazis_project',
  
  /** Maximum stored versions to keep */
  MAX_VERSIONS: 10,
} as const;

// ============================================================================
// TOAST NOTIFICATION CONFIGURATION
// ============================================================================

export const TOAST_CONFIG = {
  /** Toast display duration (milliseconds) */
  DURATION_MS: 4000,
  
  /** Success toast duration (milliseconds) */
  SUCCESS_DURATION_MS: 3000,
  
  /** Error toast duration (milliseconds) */
  ERROR_DURATION_MS: 5000,
} as const;

// ============================================================================
// MATERIAL DEFAULTS
// ============================================================================

export const MATERIAL_CONFIG = {
  /** Default edge thickness (mm) */
  DEFAULT_EDGE_THICKNESS: 2,
  
  /** Body edge thickness (mm) */
  BODY_EDGE_THICKNESS: 0.4,
  
  /** Standard material density (kg/m3) - particle board */
  PARTICLE_BOARD_DENSITY: 750,
} as const;

// ============================================================================
// PERFORMANCE CONFIGURATION
// ============================================================================

export const PERFORMANCE_CONFIG = {
  /** Maximum panels to render simultaneously */
  MAX_PANELS_RENDER: 100,
  
  /** Camera far plane (units) */
  CAMERA_FAR: 100000,
  
  /** Camera near plane (units) */
  CAMERA_NEAR: 1,
} as const;
