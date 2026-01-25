
import { GoogleGenAI } from "@google/genai";
import { Panel, CabinetConfig, Section, Material, Axis, Hardware } from "../types";

// ============================================================================
// 1. CONFIGURATION & PROMPTS
// ============================================================================

const GEMINI_CONFIG = {
  MODEL_ID: "gemini-3-flash-preview",
  PRO_MODEL_ID: "gemini-3-pro-preview",
  RETRY: {
    MAX_RETRIES: 3,
    INITIAL_DELAY_MS: 1000,
    MAX_DELAY_MS: 15000,
    EXPONENTIAL_BASE: 2,
    JITTER_MS: 500,
  }
};

const SYSTEM_PROMPTS = {
  GENERATOR: `
    ROLE: Furniture Engineer / CAD Automation Specialist.
    TASK: Convert the user's natural language request into a precise parametric JSON configuration.
    
    CONSTRAINTS:
    - Default Depth: 600mm (Wardrobe), 350mm (Bookshelf).
    - Default Height: 2400mm.
    - Default Material: 'eg-w980' if unspecified.
    - Drawer Height: Standard 176mm unless specified.
    - HardwareType: 'confirmat' by default.
    - Sections: Distribute width evenly unless specified.
    
    OUTPUT FORMAT: 
    Raw JSON matching the interface: { config: CabinetConfig, sections: Section[] }.
    Do NOT use Markdown code blocks.
  `,
  
  AUDITOR: `
    ROLE: Chief Furniture Technologist.
    
    KNOWLEDGE BASE (FURNITURE STANDARDS):
    1. SHELF DEFLECTION: Particle Board 16mm max span is 700mm (light) or 550mm (heavy). >800mm is a CRITICAL ERROR.
    2. HINGES: <900mm (2), 900-1600mm (3), 1600-2000mm (4), >2000mm (5).
    3. DRAWERS: Internal depth must be cabinet depth - 10mm minimum.
    4. EDGING: Floor contact parts must be edged. Visible edges 2mm, body 0.4mm.
    5. RIGIDITY: Tall cabinets (>2000mm) need fixed horizons or stiffeners.
    6. GEOMETRY: Intersecting panels are physically impossible. Check the "AUTOMATED PRE-CHECKS" section carefully. If collisions are listed, prioritize reporting them as CRITICAL ERRORS with coordinates.
    
    TASK: Perform a "Soft-Check" (Efficiency) and "Hard-Check" (Safety/Physics).
    REPORTING: concise, professional, in Russian language.
  `,

  EXPERT: `
    ROLE: Senior Furniture Technologist & Carpenter (Expert Mentor).
    LANGUAGE: Russian.
    
    TASK: Answer general questions about furniture construction, ergonomics, hardware standards, and best practices.
    
    KNOWLEDGE BASE:
    - Ergonomics: Table heights (750mm), Kitchen base (860-910mm), Hanging rod heights (1600mm long/1000mm short).
    - Construction: System 32, Material properties (Laminated Chipboard, MDF), Gap standards (2-3mm for fronts).
    - Hardware: Blum, Hettich, GTV standards. Minifix layout, Hinge calculations.
    
    STYLE:
    - Concise, practical, and technical.
    - Use Metric System (mm) exclusively.
    - Provide specific numbers and ranges.
    - Do NOT generate JSON or code, just helpful text explanations.
  `,

  VISION: `
    ROLE: Expert Furniture Technologist & Design Analyzer.
    LANGUAGE: Russian.
    TASK: Analyze the provided image of furniture, sketches, or technical drawings.
    
    IDENTIFY:
    1. Type of furniture (Wardrobe, Kitchen, Table, etc.).
    2. Probable Materials & Textures (e.g., White Gloss, Oak, Concrete, Metal).
    3. Construction method (Box structure, Built-in, Modular).
    4. Visible Hardware (Handles, hinges, sliding systems).
    
    OUTPUT:
    - Concise breakdown of what is visible.
    - Suggestions for replication using standard 16mm Laminated Chipboard.
    - Estimated dimensions if context allows.
    - Potential technical challenges for this design.
  `
};

// ============================================================================
// 2. TYPES & INTERFACES
// ============================================================================

export interface ProjectAnalysisData {
    panels: Panel[];
    stats: {
        totalArea: number;
        estimatedSheets: number;
        materialCount: number;
        uniqueParts: number;
    };
    hardwareSummary: Record<string, number>;
    materials: string[];
    collisions?: string[];
}

export interface GeneratorResult {
    config: CabinetConfig;
    sections: Section[];
}

export type ConnectionType = 'confirmat' | 'minifix' | 'dowel_only';

export type ErrorCategory = 'QUOTA' | 'SERVER' | 'CLIENT' | 'SAFETY' | 'NETWORK' | 'UNKNOWN';

interface GeminiErrorAnalysis {
  userMessage: string;
  technicalDetails: string;
  category: ErrorCategory;
  canRetry: boolean;
  minWaitMs: number;
}

// Helper interface for geometric calculations
interface PanelBox {
    id: string;
    minX: number; maxX: number;
    minY: number; maxY: number;
    minZ: number; maxZ: number;
    type: 'vertical' | 'horizontal' | 'frontal';
    panel: Panel;
}

// ============================================================================
// 3. UTILITIES (Pure Functions)
// ============================================================================

/**
 * Cleans the AI response string to ensure valid JSON parsing.
 * Removes Markdown code blocks and comments.
 */
const cleanJsonResponse = (text: string | undefined): string => {
  if (!text) return "{}";
  let clean = text;
  
  // Extract content from Markdown code blocks if present
  const codeBlockMatch = clean.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  if (codeBlockMatch && codeBlockMatch[1]) {
      clean = codeBlockMatch[1];
  }
  
  // Find the JSON object boundaries
  const firstOpenBrace = clean.indexOf('{');
  const lastCloseBrace = clean.lastIndexOf('}');
  
  if (firstOpenBrace !== -1 && lastCloseBrace !== -1) {
    clean = clean.substring(firstOpenBrace, lastCloseBrace + 1);
  }
  
  return clean
    .replace(/,(\s*[}\]])/g, '$1') // Remove trailing commas
    .replace(/\/\*[\s\S]*?\*\//g, '') // Remove multi-line comments
    .replace(/(^|[^\\:])\/\/.*$/gm, '$1') // Remove single-line comments
    .trim();
};

/**
 * Generates a unique ID for hardware items.
 */
const generateId = (prefix: string) => `${prefix}-${Math.random().toString(36).substr(2, 6)}`;

/**
 * Classifies API errors to determine retry strategy.
 */
const classifyError = (error: any): GeminiErrorAnalysis => {
  const msg = (error.message || error.toString()).toLowerCase();
  const status = error.status || error.response?.status;

  if (msg.includes('safety') || msg.includes('blocked') || msg.includes('policy')) {
      return {
          userMessage: "Запрос отклонен фильтрами безопасности AI. Попробуйте переформулировать запрос.",
          technicalDetails: `Safety/Policy: ${msg}`,
          category: 'SAFETY',
          canRetry: false,
          minWaitMs: 0
      };
  }

  if (msg.includes('api key') || status === 403 || msg.includes('location') || msg.includes('region')) {
      return { 
          userMessage: "Ошибка доступа. Проверьте API ключ. Сервис недоступен в вашем регионе (требуется VPN).", 
          technicalDetails: `403/Auth: ${msg}`, 
          category: 'CLIENT', 
          canRetry: false, 
          minWaitMs: 0 
      };
  }
  
  if (status === 429 || msg.includes('quota') || msg.includes('exhausted') || msg.includes('limit')) {
      return { 
          userMessage: "Превышен лимит запросов. Пожалуйста, подождите...", 
          technicalDetails: `429/Quota: ${msg}`, 
          category: 'QUOTA', 
          canRetry: true, 
          minWaitMs: 5000 
      };
  }
  
  if (status >= 500) {
      return { 
          userMessage: "Сервис Google AI временно перегружен. Повторная попытка...", 
          technicalDetails: `5xx/Server: ${msg}`, 
          category: 'SERVER', 
          canRetry: true, 
          minWaitMs: 2000 
      };
  }

  if (msg.includes('fetch') || msg.includes('network') || msg.includes('connection') || msg.includes('offline')) {
      return {
          userMessage: "Нет связи с сервером. Проверьте интернет-соединение.",
          technicalDetails: `Network: ${msg}`,
          category: 'NETWORK',
          canRetry: true,
          minWaitMs: 3000
      };
  }
  
  return { 
      userMessage: "Произошла ошибка при генерации. Попробуйте еще раз.", 
      technicalDetails: `Unknown: ${msg}`, 
      category: 'UNKNOWN', 
      canRetry: true, 
      minWaitMs: 1000 
  };
};

/**
 * Calculates the bounding box for a panel based on its rotation.
 */
const getPanelBox = (p: Panel): PanelBox => {
    let dX = 0, dY = 0, dZ = 0;
    if (p.rotation === Axis.X) { dX = p.depth; dY = p.height; dZ = p.width; }
    else if (p.rotation === Axis.Y) { dX = p.width; dY = p.depth; dZ = p.height; }
    else { dX = p.width; dY = p.height; dZ = p.depth; }

    let type: PanelBox['type'] = 'horizontal';
    if (p.rotation === Axis.X) type = 'vertical'; 
    if (p.rotation === Axis.Z) type = 'frontal'; 

    return {
        id: p.id,
        minX: p.x, maxX: p.x + dX,
        minY: p.y, maxY: p.y + dY,
        minZ: p.z, maxZ: p.z + dZ,
        type,
        panel: p
    };
};

// ============================================================================
// 4. GEOMETRY LOGIC (Hardware Calculation)
// ============================================================================

/**
 * Calculates hardware positions based on panel intersections.
 * This is a deterministic geometric algorithm, not AI-based.
 */
const calculateHardwarePlacement = (panels: Panel[], connectionType: ConnectionType): Panel[] => {
    const processedPanels: Panel[] = JSON.parse(JSON.stringify(panels));
    
    // 1. Cleanup existing structural hardware
    processedPanels.forEach(p => {
        if (p.hardware) {
            // Preserve functional hardware (handles, rails, etc.)
            p.hardware = p.hardware.filter(h => 
                ['handle', 'slide_rail', 'hinge_cup', 'pantograph', 'rod_holder', 'basket_rail', 'legs'].includes(h.type)
            );
        } else {
            p.hardware = [];
        }
    });

    // 2. Prepare bounding boxes for analysis
    const boxes = processedPanels.map(getPanelBox);
    const tolerance = 2.0;

    const verticalPanels = boxes.filter(b => b.type === 'vertical' && b.panel.layer === 'body');
    const horizontalPanels = boxes.filter(b => b.type === 'horizontal' && (b.panel.layer === 'body' || b.panel.layer === 'shelves'));

    // 3. Find Intersections & Add Hardware
    for (const ver of verticalPanels) {
        for (const hor of horizontalPanels) {
            if (ver.id === hor.id) continue;

            // Check overlap depth (Z-axis overlap)
            const zOverlapStart = Math.max(ver.minZ, hor.minZ);
            const zOverlapEnd = Math.min(ver.maxZ, hor.maxZ);
            const overlapDepth = zOverlapEnd - zOverlapStart;
            
            if (overlapDepth < 50) continue; // Ignore minimal overlaps

            // Check vertical alignment (Horizontal is "inside" Vertical's Y-range)
            const isInsideY = (hor.minY >= ver.minY - tolerance) && (hor.maxY <= ver.maxY + tolerance);
            if (!isInsideY) continue;

            // Check butt joint (Left or Right side of Horizontal touches Vertical face)
            const leftButt = Math.abs(hor.minX - ver.maxX) < tolerance;
            const rightButt = Math.abs(hor.maxX - ver.minX) < tolerance;

            if (leftButt || rightButt) {
                addJointHardware(ver, hor, connectionType, zOverlapStart, overlapDepth, leftButt);
            }
        }
    }

    return processedPanels;
};

/**
 * Adds drilling operations for a specific joint between a vertical and horizontal panel.
 */
const addJointHardware = (
    ver: PanelBox, 
    hor: PanelBox, 
    type: ConnectionType, 
    zStart: number, 
    depth: number, 
    isLeftButt: boolean
) => {
    // Coordinate mapping:
    // Vertical Panel (Rot X): Local X = Depth (Z in World), Local Y = Height (Y in World)
    // Horizontal Panel (Rot Y): Local X = Width (X in World), Local Y = Depth (Z in World)

    const holeY_Side = (hor.minY + hor.maxY) / 2 - ver.minY;
    const holeZ_Start_Side = zStart - ver.minZ;
    
    const offset = 50; // Standard distance from front/back edges
    const z1 = holeZ_Start_Side + offset;
    const z2 = holeZ_Start_Side + depth - offset;

    // --- Vertical Panel Holes (Face Drilling) ---
    if (type === 'confirmat') {
        ver.panel.hardware.push({ id: generateId('sc-f'), type: 'screw', name: 'Конфирмат', x: z1, y: holeY_Side, diameter: 5, isThrough: true });
        ver.panel.hardware.push({ id: generateId('sc-b'), type: 'screw', name: 'Конфирмат', x: z2, y: holeY_Side, diameter: 5, isThrough: true });
    } else if (type === 'minifix') {
        ver.panel.hardware.push({ id: generateId('mf-p-f'), type: 'minifix_pin', name: 'Шток эксц.', x: z1, y: holeY_Side, diameter: 5 });
        ver.panel.hardware.push({ id: generateId('mf-p-b'), type: 'minifix_pin', name: 'Шток эксц.', x: z2, y: holeY_Side, diameter: 5 });
        // Dowels typically added alongside minifix for alignment
        ver.panel.hardware.push({ id: generateId('dw-f'), type: 'dowel_hole', name: 'Шкант', x: z1 + 32, y: holeY_Side, diameter: 8, depth: 12 });
        ver.panel.hardware.push({ id: generateId('dw-b'), type: 'dowel_hole', name: 'Шкант', x: z2 - 32, y: holeY_Side, diameter: 8, depth: 12 });
    }

    // --- Horizontal Panel Holes (Edge Drilling/Face Cams) ---
    const shelfHoleY1 = offset; 
    const shelfHoleY2 = depth - offset; 
    
    // Determine which side of the shelf is being drilled (0 or Width)
    const holeX_Shelf = isLeftButt ? 0 : hor.panel.width;

    if (type === 'confirmat') {
        hor.panel.hardware.push({ id: generateId('sc-end-f'), type: 'screw', name: 'Отв. конфирмат', x: holeX_Shelf, y: shelfHoleY1, diameter: 5, depth: 40 });
        hor.panel.hardware.push({ id: generateId('sc-end-b'), type: 'screw', name: 'Отв. конфирмат', x: holeX_Shelf, y: shelfHoleY2, diameter: 5, depth: 40 });
    } else if (type === 'minifix') {
        // Minifix Cams are on the face, usually 34mm from the edge
        const camOffset = isLeftButt ? 34 : hor.panel.width - 34;
        
        hor.panel.hardware.push({ id: generateId('mf-cam-f'), type: 'minifix_cam', name: 'Эксцентрик', x: camOffset, y: shelfHoleY1, diameter: 15, depth: 13 });
        hor.panel.hardware.push({ id: generateId('mf-cam-b'), type: 'minifix_cam', name: 'Эксцентрик', x: camOffset, y: shelfHoleY2, diameter: 15, depth: 13 });
        
        // Edge holes for the pin shaft
        hor.panel.hardware.push({ id: generateId('mf-pin-hole-f'), type: 'dowel_hole', name: 'Отв. шток', x: holeX_Shelf, y: shelfHoleY1, diameter: 8, depth: 34 });
        hor.panel.hardware.push({ id: generateId('mf-pin-hole-b'), type: 'dowel_hole', name: 'Отв. шток', x: holeX_Shelf, y: shelfHoleY2, diameter: 8, depth: 34 });

        // Dowel holes in edge
        hor.panel.hardware.push({ id: generateId('dw-end-f'), type: 'dowel_hole', name: 'Отв. шкант', x: holeX_Shelf, y: shelfHoleY1 + 32, diameter: 8, depth: 30 });
        hor.panel.hardware.push({ id: generateId('dw-end-b'), type: 'dowel_hole', name: 'Отв. шкант', x: holeX_Shelf, y: shelfHoleY2 - 32, diameter: 8, depth: 30 });
    }
};

// ============================================================================
// 5. AI SERVICE CLASS
// ============================================================================

export class GeminiCabinetService {
  private client: GoogleGenAI;

  constructor(apiKey: string) {
    this.client = new GoogleGenAI({ apiKey });
  }

  /**
   * Generates a parametric cabinet configuration from a natural language prompt.
   */
  async generateDesignConfig(prompt: string, availableMaterials: Material[]): Promise<GeneratorResult> {
    return this.executeWithRetry(async () => {
      const materialsContext = availableMaterials
        .map(m => `- ${m.id}: ${m.name} (${m.thickness}mm)`)
        .join('\n');

      const fullPrompt = `
        AVAILABLE MATERIALS (Use strict IDs from this list):
        ${materialsContext}
        
        USER REQUEST: "${prompt}"
      `;

      const response = await this.client.models.generateContent({
        model: GEMINI_CONFIG.MODEL_ID,
        contents: fullPrompt,
        config: { 
            systemInstruction: SYSTEM_PROMPTS.GENERATOR, 
            responseMimeType: "application/json" 
        }
      });

      if (!response.text) {
          throw new Error("Empty response from AI model.");
      }

      const jsonStr = cleanJsonResponse(response.text);
      let result: GeneratorResult;
      
      try {
          result = JSON.parse(jsonStr);
      } catch (e) {
          console.error("JSON Parse Error:", jsonStr);
          throw new Error("AI returned malformed JSON.");
      }

      if (!result.config || !result.sections) {
          throw new Error("AI returned incomplete configuration structure.");
      }
      return result;
    });
  }

  /**
   * Performs a technical audit of the project using the AI persona.
   */
  async performTechnicalAudit(data: ProjectAnalysisData): Promise<string> {
      return this.executeWithRetry(async () => {
          const context = this.buildAuditContext(data);
          const response = await this.client.models.generateContent({
              model: GEMINI_CONFIG.MODEL_ID,
              contents: context,
              config: { systemInstruction: SYSTEM_PROMPTS.AUDITOR }
          });
          return response.text || "Не удалось сгенерировать отчет (пустой ответ).";
      });
  }

  /**
   * Consults the expert persona for general construction questions.
   */
  async consultExpert(question: string): Promise<string> {
      return this.executeWithRetry(async () => {
          const response = await this.client.models.generateContent({
              model: GEMINI_CONFIG.MODEL_ID,
              contents: question,
              config: { systemInstruction: SYSTEM_PROMPTS.EXPERT }
          });
          return response.text || "Ответ не сгенерирован.";
      });
  }

  /**
   * Analyzes an uploaded image using Gemini 3 Pro Vision capabilities.
   */
  async analyzeImage(prompt: string, imageBase64: string, mimeType: string): Promise<string> {
      return this.executeWithRetry(async () => {
          const response = await this.client.models.generateContent({
              model: GEMINI_CONFIG.PRO_MODEL_ID,
              contents: {
                  parts: [
                      { inlineData: { mimeType, data: imageBase64 } },
                      { text: prompt || "Проанализируй это изображение. Определи тип мебели, материалы и конструктивные особенности." }
                  ]
              },
              config: { systemInstruction: SYSTEM_PROMPTS.VISION }
          });
          return response.text || "Не удалось проанализировать изображение.";
      });
  }

  /**
   * Prepares the context string for the auditor AI.
   */
  private buildAuditContext(data: ProjectAnalysisData): string {
      const widePanels = data.panels.filter(p => p.width > 800 && p.height < 50 && p.layer === 'shelves');
      const tallDoors = data.panels.filter(p => p.height > 2000 && p.layer === 'facade');
      
      const simplifiedPanels = data.panels.slice(0, 50).map(p => ({
          id: p.id.slice(-4),
          name: p.name,
          dims: `${p.width}x${p.height}x${p.depth}`,
          layer: p.layer,
          mat: p.materialId,
          hw: p.hardware.map(h => h.type).join(','),
          groove: p.groove?.enabled ? 'yes' : 'no'
      }));

      return `
          PROJECT DATA FOR AUDIT:
          
          STATS:
          - Total Parts: ${data.panels.length}
          - Material Area: ${data.stats.totalArea.toFixed(2)} m²
          - Est. Sheets: ${data.stats.estimatedSheets}
          - Materials Used: ${data.materials.join(', ')}
          
          AUTOMATED PRE-CHECKS:
          - Collisions: ${data.collisions?.length ? 'YES' : 'NONE'}
          ${data.collisions?.length ? `DETAILS: ${data.collisions.join('; ')}` : ''}
          - Wide Shelves (>800mm): ${widePanels.length}
          - Tall Doors (>2m): ${tallDoors.length}
          
          HARDWARE SUMMARY:
          ${JSON.stringify(data.hardwareSummary, null, 2)}

          PARTS LIST (Sample):
          ${JSON.stringify(simplifiedPanels, null, 2)}
      `;
  }

  /**
   * Wrapper for API calls with Exponential Backoff + Jitter and Smart Error Handling.
   */
  private async executeWithRetry<T>(fn: () => Promise<T>): Promise<T> {
    let lastError: any;
    
    for (let attempt = 0; attempt < GEMINI_CONFIG.RETRY.MAX_RETRIES; attempt++) {
      try {
        return await fn();
      } catch (error: unknown) {
        lastError = error;
        const analysis = classifyError(error);
        
        console.warn(`Gemini API Attempt ${attempt + 1} failed:`, analysis.technicalDetails);

        if (!analysis.canRetry) {
            throw new Error(analysis.userMessage);
        }
        
        if (attempt === GEMINI_CONFIG.RETRY.MAX_RETRIES - 1) {
            throw new Error(analysis.userMessage);
        }

        // Exponential Backoff with Jitter
        const exponentialDelay = analysis.minWaitMs * Math.pow(GEMINI_CONFIG.RETRY.EXPONENTIAL_BASE, attempt);
        const jitter = Math.random() * GEMINI_CONFIG.RETRY.JITTER_MS;
        const delay = Math.min(GEMINI_CONFIG.RETRY.MAX_DELAY_MS, exponentialDelay + jitter);
        
        await new Promise(r => setTimeout(r, delay));
      }
    }
    throw lastError;
  }
}

// ============================================================================
// 6. EXPORTS (Singleton & Functions)
// ============================================================================

let instance: GeminiCabinetService | null = null;

/**
 * Initializes the AI Service with the API Key.
 */
export const initializeGemini = (apiKey: string) => { 
    instance = new GeminiCabinetService(apiKey); 
};

/**
 * Gets the singleton instance of the service.
 */
export const getGeminiService = (): GeminiCabinetService => { 
    if (!instance) throw new Error("AI Service not initialized. Check API Key."); 
    return instance; 
};

/**
 * Public wrapper to generate cabinet configuration.
 */
export const generateCabinetConfig = async (prompt: string, materials: Material[]) => {
    return getGeminiService().generateDesignConfig(prompt, materials);
}

/**
 * Public wrapper to consult the expert.
 */
export const askExpert = async (question: string): Promise<string> => {
    return getGeminiService().consultExpert(question);
};

/**
 * Public wrapper to analyze image.
 */
export const analyzeImage = async (prompt: string, imageBase64: string, mimeType: string): Promise<string> => {
    return getGeminiService().analyzeImage(prompt, imageBase64, mimeType);
};

/**
 * Public wrapper to analyze the project.
 */
export const analyzeProject = async (data: ProjectAnalysisData): Promise<string> => {
    return getGeminiService().performTechnicalAudit(data);
};

/**
 * Calculates hardware placement.
 * This is a pure geometric function and does not require AI initialization.
 */
export const autoPlaceHardware = (panels: Panel[], type: ConnectionType = 'confirmat'): Panel[] => {
    return calculateHardwarePlacement(panels, type);
};

// Legacy alias compatibility
export const optimizeCutList = analyzeProject;
