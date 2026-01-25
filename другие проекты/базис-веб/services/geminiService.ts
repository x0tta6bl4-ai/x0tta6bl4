
import { GoogleGenerativeAI, GenerateContentResponse } from "@google/generative-ai";
import { Panel, CabinetConfig, Section, Material, Axis } from "../types";

// ============================================================================
// 1. CONFIGURATION & CONSTANTS
// ============================================================================

const GEMINI_CONFIG = {
  MODEL_ID: "gemini-2.0-flash",
  RETRY: {
    MAX_RETRIES: 3,
    INITIAL_DELAY_MS: 1000,
    MAX_DELAY_MS: 15000,
    EXPONENTIAL_BASE: 2,
    JITTER_MS: 500, // Randomness to avoid thundering herd
  },
  TIMEOUT_MS: 30000,  // 30 second timeout for API calls
  CACHE: {
    ENABLED: true,
    TTL_MS: 3600000, // 1 hour cache for system prompts
    MAX_SIZE: 10, // Maximum cached models
  },
  STREAMING: {
    ENABLED: true,
    CHUNK_SIZE: 1024, // Process chunks of this size
  },
  DEDUPLICATION: {
    ENABLED: true,
    TTL_MS: 300000, // 5 minutes cache for identical requests
    MAX_SIZE: 50, // Maximum deduplication cache size
  },
  MONITORING: {
    ENABLED: true,
    LOG_PERFORMANCE: true,
    TRACK_METRICS: true,
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
    6. GEOMETRY: Intersecting panels are physically impossible.
    
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

export type ErrorCategory = 'QUOTA' | 'SERVER' | 'CLIENT' | 'SAFETY' | 'NETWORK' | 'UNKNOWN';

export interface GeminiErrorAnalysis {
  userMessage: string;
  technicalDetails: string;
  category: ErrorCategory;
  canRetry: boolean;
  minWaitMs: number;
}

export interface GeneratorResult {
    config: CabinetConfig;
    sections: Section[];
}

type ConnectionType = 'confirmat' | 'minifix' | 'dowel_only';

// ============================================================================
// CACHE SYSTEM
// ============================================================================

interface CachedModel {
  model: any; // GoogleGenerativeAI model instance
  createdAt: number;
  systemPrompt: string;
}

class ModelCache {
  private cache = new Map<string, CachedModel>();
  private accessOrder: string[] = [];

  get(key: string): CachedModel | undefined {
    const item = this.cache.get(key);
    if (item && this.isExpired(item)) {
      this.cache.delete(key);
      this.accessOrder = this.accessOrder.filter(k => k !== key);
      return undefined;
    }
    if (item) {
      // Move to end (most recently used)
      this.accessOrder = this.accessOrder.filter(k => k !== key);
      this.accessOrder.push(key);
    }
    return item;
  }

  set(key: string, model: any, systemPrompt: string): void {
    if (this.cache.size >= GEMINI_CONFIG.CACHE.MAX_SIZE) {
      const oldestKey = this.accessOrder.shift();
      if (oldestKey) {
        this.cache.delete(oldestKey);
      }
    }

    this.cache.set(key, {
      model,
      createdAt: Date.now(),
      systemPrompt
    });
    this.accessOrder.push(key);
  }

  private isExpired(item: CachedModel): boolean {
    return Date.now() - item.createdAt > GEMINI_CONFIG.CACHE.TTL_MS;
  }

  clear(): void {
    this.cache.clear();
    this.accessOrder = [];
  }
}

class RequestDeduplicationCache {
  private cache = new Map<string, { result: any; timestamp: number }>();

  get(key: string): any | undefined {
    const item = this.cache.get(key);
    if (item && this.isExpired(item)) {
      this.cache.delete(key);
      return undefined;
    }
    return item?.result;
  }

  set(key: string, result: any): void {
    if (this.cache.size >= GEMINI_CONFIG.DEDUPLICATION.MAX_SIZE) {
      // Remove oldest entry (simple FIFO)
      const firstKey = this.cache.keys().next().value;
      if (firstKey) {
        this.cache.delete(firstKey);
      }
    }

    this.cache.set(key, {
      result,
      timestamp: Date.now()
    });
  }

  private isExpired(item: { result: any; timestamp: number }): boolean {
    return Date.now() - item.timestamp > GEMINI_CONFIG.DEDUPLICATION.TTL_MS;
  }

  clear(): void {
    this.cache.clear();
  }
}

interface PanelBox {
    id: string;
    minX: number; maxX: number;
    minY: number; maxY: number;
    minZ: number; maxZ: number;
    type: 'vertical' | 'horizontal' | 'frontal';
    panel: Panel;
}

// ============================================================================
// 3. UTILITIES
// ============================================================================

const cleanJsonResponse = (text: string | undefined): string => {
  if (!text) return "{}";
  let clean = text;
  
  // Remove Markdown code blocks
  const codeBlockMatch = clean.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  if (codeBlockMatch && codeBlockMatch[1]) {
      clean = codeBlockMatch[1];
  }
  
  // Attempt to isolate the JSON object if there is extra text around it
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
 * Wraps a promise with a timeout mechanism
 * @param promise The promise to wrap
 * @param timeoutMs Timeout in milliseconds
 * @param operationName Optional name of the operation for error messages
 * @returns Promise that rejects if timeout is exceeded
 */
const withTimeout = async <T>(
  promise: Promise<T>,
  timeoutMs: number,
  operationName: string = "Operation"
): Promise<T> => {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) =>
      setTimeout(
        () => reject(
          new Error(
            `${operationName} timed out after ${timeoutMs}ms. ` +
            `The server may be overloaded or the network connection is slow.`
          )
        ),
        timeoutMs
      )
    )
  ]);
};

/**
 * Advanced error classification based on Google GenAI error patterns and HTTP status codes.
 */
const classifyError = (error: any): GeminiErrorAnalysis => {
  const msg = (error.message || error.toString()).toLowerCase();
  const status = error.status || error.response?.status;

  // 1. Safety / Policy Violations (often 400 or block reason in response)
  if (msg.includes('safety') || msg.includes('blocked') || msg.includes('policy')) {
      return {
          userMessage: "Запрос отклонен фильтрами безопасности AI. Попробуйте переформулировать запрос.",
          technicalDetails: `Safety/Policy: ${msg}`,
          category: 'SAFETY',
          canRetry: false,
          minWaitMs: 0
      };
  }

  // 2. Authentication / Geo-blocking
  if (msg.includes('api key') || status === 403 || msg.includes('location') || msg.includes('region')) {
      return { 
          userMessage: "Ошибка доступа. Проверьте API ключ. Сервис недоступен в вашем регионе (требуется VPN).", 
          technicalDetails: `403/Auth: ${msg}`, 
          category: 'CLIENT', 
          canRetry: false, 
          minWaitMs: 0 
      };
  }
  
  // 3. Quota Exceeded (429)
  if (status === 429 || msg.includes('quota') || msg.includes('exhausted') || msg.includes('limit')) {
      return { 
          userMessage: "Превышен лимит запросов. Пожалуйста, подождите...", 
          technicalDetails: `429/Quota: ${msg}`, 
          category: 'QUOTA', 
          canRetry: true, 
          minWaitMs: 5000 
      };
  }
  
  // 4. Server Errors (5xx)
  if (status >= 500) {
      return { 
          userMessage: "Сервис Google AI временно перегружен. Повторная попытка...", 
          technicalDetails: `5xx/Server: ${msg}`, 
          category: 'SERVER', 
          canRetry: true, 
          minWaitMs: 2000 
      };
  }

  // 5. Network / Offline
  if (msg.includes('fetch') || msg.includes('network') || msg.includes('connection') || msg.includes('offline')) {
      return {
          userMessage: "Нет связи с сервером. Проверьте интернет-соединение.",
          technicalDetails: `Network: ${msg}`,
          category: 'NETWORK',
          canRetry: true,
          minWaitMs: 3000
      };
  }
  
  // 6. Default Fallback
  return { 
      userMessage: "Произошла ошибка при генерации. Попробуйте еще раз.", 
      technicalDetails: `Unknown: ${msg}`, 
      category: 'UNKNOWN', 
      canRetry: true, 
      minWaitMs: 1000 
  };
};

const generateId = (prefix: string) => `${prefix}-${Math.random().toString(36).substr(2, 6)}`;

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
// 4. SERVICE CLASS
// ============================================================================

export class GeminiCabinetService {
  private client: GoogleGenerativeAI;
  private modelCache: ModelCache;
  private deduplicationCache: RequestDeduplicationCache;
  private metrics: {
    requests: number;
    cacheHits: number;
    deduplicationHits: number;
    errors: number;
    totalResponseTime: number;
  };

  constructor(apiKey: string) {
    this.client = new GoogleGenerativeAI(apiKey);
    this.modelCache = new ModelCache();
    this.deduplicationCache = new RequestDeduplicationCache();
    this.metrics = {
      requests: 0,
      cacheHits: 0,
      deduplicationHits: 0,
      errors: 0,
      totalResponseTime: 0,
    };
  }

  /**
   * Get or create a cached model with system instructions
   */
  private getCachedModel(systemPrompt: string): any {
    if (!GEMINI_CONFIG.CACHE.ENABLED) {
      return this.client.getGenerativeModel({
        model: GEMINI_CONFIG.MODEL_ID,
        systemInstruction: systemPrompt
      });
    }

    const cacheKey = `${GEMINI_CONFIG.MODEL_ID}:${systemPrompt.slice(0, 100)}`; // Use first 100 chars as key
    let cached = this.modelCache.get(cacheKey);

    if (cached) {
      this.metrics.cacheHits++;
      if (GEMINI_CONFIG.MONITORING.LOG_PERFORMANCE) {
        console.log(`💾 Model cache hit for: ${cacheKey}`);
      }
    } else {
      const model = this.client.getGenerativeModel({
        model: GEMINI_CONFIG.MODEL_ID,
        systemInstruction: systemPrompt
      });
      this.modelCache.set(cacheKey, model, systemPrompt);
      cached = this.modelCache.get(cacheKey);
      if (GEMINI_CONFIG.MONITORING.LOG_PERFORMANCE) {
        console.log(`🆕 Model cache miss, created new model for: ${cacheKey}`);
      }
    }

    return cached?.model;
  }

  /**
   * Generate a cache key for request deduplication
   */
  private generateRequestKey(method: string, ...args: any[]): string {
    const argsStr = args.map(arg => typeof arg === 'string' ? arg : JSON.stringify(arg)).join('|');
    return `${method}:${argsStr.slice(0, 200)}`; // Limit key length
  }

  /**
   * Execute with deduplication check
   */
  private async executeWithDeduplication<T>(
    cacheKey: string,
    operation: () => Promise<T>
  ): Promise<T> {
    const startTime = Date.now();

    if (GEMINI_CONFIG.DEDUPLICATION.ENABLED) {
      const cachedResult = this.deduplicationCache.get(cacheKey);
      if (cachedResult !== undefined) {
        this.metrics.deduplicationHits++;
        if (GEMINI_CONFIG.MONITORING.LOG_PERFORMANCE) {
          console.log(`🔄 Deduplication hit for: ${cacheKey} (${Date.now() - startTime}ms)`);
        }
        return cachedResult;
      }
    }

    this.metrics.requests++;
    const result = await operation();
    const duration = Date.now() - startTime;
    this.metrics.totalResponseTime += duration;

    if (GEMINI_CONFIG.DEDUPLICATION.ENABLED) {
      this.deduplicationCache.set(cacheKey, result);
    }

    if (GEMINI_CONFIG.MONITORING.LOG_PERFORMANCE) {
      console.log(`🤖 AI Request completed: ${duration}ms`);
    }

    return result;
  }

  /**
   * Get performance metrics
   */
  public getMetrics() {
    const avgResponseTime = this.metrics.requests > 0
      ? this.metrics.totalResponseTime / this.metrics.requests
      : 0;

    return {
      ...this.metrics,
      averageResponseTime: Math.round(avgResponseTime),
      cacheHitRate: this.metrics.requests > 0
        ? Math.round((this.metrics.cacheHits / this.metrics.requests) * 100)
        : 0,
      deduplicationHitRate: this.metrics.requests > 0
        ? Math.round((this.metrics.deduplicationHits / this.metrics.requests) * 100)
        : 0,
      errorRate: this.metrics.requests > 0
        ? Math.round((this.metrics.errors / this.metrics.requests) * 100)
        : 0,
    };
  }

  /**
   * Reset metrics (useful for testing)
   */
  public resetMetrics() {
    this.metrics = {
      requests: 0,
      cacheHits: 0,
      deduplicationHits: 0,
      errors: 0,
      totalResponseTime: 0,
    };
  }

  /**
   * Generates a parametric cabinet configuration from a natural language prompt.
   */
  async createDesignFromPrompt(prompt: string, availableMaterials: Material[]): Promise<GeneratorResult> {
    return this.executeWithRetry(async () => {
      const materialsContext = availableMaterials
        .map(m => `- ${m.id}: ${m.name} (${m.thickness}mm)`)
        .join('\n');

      const fullPrompt = `
        AVAILABLE MATERIALS (Use strict IDs from this list):
        ${materialsContext}
        
        USER REQUEST: "${prompt}"
      `;

      const model = this.getCachedModel(SYSTEM_PROMPTS.GENERATOR);

      const response: GenerateContentResponse = await withTimeout(
        model.generateContent(fullPrompt),
        GEMINI_CONFIG.TIMEOUT_MS,
        "Design generation"
      );

      const responseText = (response as any).response?.text?.() || (response as any).text?.() || "";
      if (!responseText) {
          throw new Error("Empty response from AI model.");
      }

      const jsonStr = cleanJsonResponse(responseText);
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
   * Performs a technical audit of the project.
   */
  async conductTechnicalAudit(data: ProjectAnalysisData): Promise<string> {
      return this.executeWithRetry(async () => {
          const context = this.prepareAuditContext(data);
          const model = this.getCachedModel(SYSTEM_PROMPTS.AUDITOR);
          const response = await withTimeout(
            model.generateContent(context),
            GEMINI_CONFIG.TIMEOUT_MS,
            "Technical audit"
          );
          return (response as any).response?.text?.() || (response as any).text?.() || "Не удалось сгенерировать отчет (пустой ответ).";
      });
  }

  /**
   * Asks the expert persona general construction questions.
   */
  async askFurnitureExpert(question: string): Promise<string> {
    const cacheKey = this.generateRequestKey('askFurnitureExpert', question);

    return this.executeWithDeduplication(cacheKey, async () => {
      return this.executeWithRetry(async () => {
        const model = this.getCachedModel(SYSTEM_PROMPTS.EXPERT);
        const response = await withTimeout(
          model.generateContent(question),
          GEMINI_CONFIG.TIMEOUT_MS,
          "Expert consultation"
        );
        return (response as any).response?.text?.() || (response as any).text?.() || "Ответ не сгенерирован.";
      });
    });
  }

  /**
   * Streaming version of askFurnitureExpert for real-time responses
   */
  async askFurnitureExpertStreaming(
    question: string,
    onChunk?: (chunk: string) => void
  ): Promise<string> {
    if (!GEMINI_CONFIG.STREAMING.ENABLED || !onChunk) {
      return this.askFurnitureExpert(question);
    }

    return this.executeWithRetry(async () => {
      const model = this.getCachedModel(SYSTEM_PROMPTS.EXPERT);
      const streamingResponse = await model.generateContentStream(question);

      let fullResponse = '';
      for await (const chunk of streamingResponse.stream) {
        const chunkText = (chunk as any).text?.() || '';
        if (chunkText) {
          fullResponse += chunkText;
          onChunk(chunkText);
        }
      }

      return fullResponse || "Ответ не сгенерирован.";
    });
  }

  /**
   * Automatically calculates and places hardware holes based on panel intersections.
   * This is a synchronous geometric algorithm (Bazis-like), no AI involved.
   */
  public autoPlaceHardware(panels: Panel[], connectionType: ConnectionType = 'confirmat'): Panel[] {
      const processedPanels: Panel[] = JSON.parse(JSON.stringify(panels));
      
      // 1. Cleanup existing hardware (except handles/functional items)
      processedPanels.forEach(p => {
          if (p.hardware) {
              // Keep functional hardware (handles, rails, etc), remove structural fasteners
              p.hardware = p.hardware.filter(h => 
                  ['handle', 'slide_rail', 'hinge_cup', 'pantograph', 'rod_holder'].includes(h.type)
              );
          } else {
              p.hardware = [];
          }
      });

      // 2. Geometric Analysis
      const boxes = processedPanels.map(getPanelBox);
      const tolerance = 2.0;

      const verticalPanels = boxes.filter(b => b.type === 'vertical' && b.panel.layer === 'body');
      const horizontalPanels = boxes.filter(b => b.type === 'horizontal' && (b.panel.layer === 'body' || b.panel.layer === 'shelves'));

      // 3. Find Intersections
      for (const ver of verticalPanels) {
          for (const hor of horizontalPanels) {
              if (ver.id === hor.id) continue;

              // Check depth overlap (must be substantial, e.g., >50mm)
              const zOverlapStart = Math.max(ver.minZ, hor.minZ);
              const zOverlapEnd = Math.min(ver.maxZ, hor.maxZ);
              const overlapDepth = zOverlapEnd - zOverlapStart;
              
              if (overlapDepth < 50) continue;

              // Check height alignment (horizontal is within vertical's bounds)
              const isInsideY = (hor.minY >= ver.minY - tolerance) && (hor.maxY <= ver.maxY + tolerance);
              if (!isInsideY) continue;

              // Check butt joint (left or right side of horizontal touches vertical face)
              const leftButt = Math.abs(hor.minX - ver.maxX) < tolerance;
              const rightButt = Math.abs(hor.maxX - ver.minX) < tolerance;

              if (leftButt || rightButt) {
                  this.addJointHardware(ver, hor, connectionType, zOverlapStart, overlapDepth, leftButt);
              }
          }
      }

      return processedPanels;
  }

  /**
   * Helper to add hardware for a specific joint.
   */
  private addJointHardware(ver: PanelBox, hor: PanelBox, type: ConnectionType, zStart: number, depth: number, isLeftButt: boolean) {
      // Local coordinates for the vertical panel (Face)
      const holeY_Side = (hor.minY + hor.maxY) / 2 - ver.minY;
      const holeZ_Start_Side = zStart - ver.minZ;
      
      const offset = 50; // Standard offset from edges
      const z1 = holeZ_Start_Side + offset;
      const z2 = holeZ_Start_Side + depth - offset;

      // Vertical Panel Holes
      if (type === 'confirmat') {
          ver.panel.hardware.push({ id: generateId('sc-f'), type: 'screw', name: 'Конфирмат', x: z1, y: holeY_Side });
          ver.panel.hardware.push({ id: generateId('sc-b'), type: 'screw', name: 'Конфирмат', x: z2, y: holeY_Side });
      } else if (type === 'minifix') {
          ver.panel.hardware.push({ id: generateId('mf-p-f'), type: 'minifix_pin', name: 'Шток эксц.', x: z1, y: holeY_Side });
          ver.panel.hardware.push({ id: generateId('mf-p-b'), type: 'minifix_pin', name: 'Шток эксц.', x: z2, y: holeY_Side });
          ver.panel.hardware.push({ id: generateId('dw-f'), type: 'dowel_hole', name: 'Шкант', x: z1 + 32, y: holeY_Side });
          ver.panel.hardware.push({ id: generateId('dw-b'), type: 'dowel_hole', name: 'Шкант', x: z2 - 32, y: holeY_Side });
      }

      // Horizontal Panel Holes (Edge)
      const shelfHoleY1 = offset; 
      const shelfHoleY2 = depth - offset; 
      
      // Determine local X for the hole (0 or width)
      const holeX_Shelf = isLeftButt ? 0 : hor.panel.width;

      if (type === 'confirmat') {
          hor.panel.hardware.push({ id: generateId('sc-end-f'), type: 'screw', name: 'Отв. конфирмат', x: holeX_Shelf, y: shelfHoleY1 });
          hor.panel.hardware.push({ id: generateId('sc-end-b'), type: 'screw', name: 'Отв. конфирмат', x: holeX_Shelf, y: shelfHoleY2 });
      } else if (type === 'minifix') {
          // Minifix Cams are usually 34mm from the edge face
          const camOffset = isLeftButt ? 34 : hor.panel.width - 34;
          hor.panel.hardware.push({ id: generateId('mf-cam-f'), type: 'minifix_cam', name: 'Эксцентрик', x: camOffset, y: shelfHoleY1 });
          hor.panel.hardware.push({ id: generateId('mf-cam-b'), type: 'minifix_cam', name: 'Эксцентрик', x: camOffset, y: shelfHoleY2 });
          
          hor.panel.hardware.push({ id: generateId('dw-end-f'), type: 'dowel_hole', name: 'Отв. шкант', x: holeX_Shelf, y: shelfHoleY1 + 32 });
          hor.panel.hardware.push({ id: generateId('dw-end-b'), type: 'dowel_hole', name: 'Отв. шкант', x: holeX_Shelf, y: shelfHoleY2 - 32 });
      }
  }

  private prepareAuditContext(data: ProjectAnalysisData): string {
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
        this.metrics.errors++;
        const analysis = classifyError(error);

        if (GEMINI_CONFIG.MONITORING.LOG_PERFORMANCE) {
          console.warn(`Gemini API Attempt ${attempt + 1} failed:`, analysis.technicalDetails);
        }

        // Immediate fail for critical client/safety errors
        if (!analysis.canRetry) {
            throw new Error(analysis.userMessage);
        }

        // If last attempt, throw helpful message
        if (attempt === GEMINI_CONFIG.RETRY.MAX_RETRIES - 1) {
            throw new Error(analysis.userMessage);
        }

        // Exponential Backoff with Jitter
        // Delay = Min(MaxDelay, (Base * 2^attempt) + Random(0..Jitter))
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
// 5. EXPORTS
// ============================================================================

let instance: GeminiCabinetService | null = null;

/**
 * 🔒 SECURITY: Initialize Gemini service with API key from environment
 * API key should NEVER be exposed in client bundle
 * It must be passed from a secure backend or environment variables
 */
export const initializeGemini = (apiKey: string) => { 
    if (!apiKey || typeof apiKey !== 'string' || apiKey.length === 0) {
        console.warn('⚠️ Gemini API Key not provided. AI features will be disabled.');
        return false;
    }
    
    if (apiKey === 'undefined' || apiKey === 'null' || apiKey.includes('[object')) {
        console.error('❌ Invalid Gemini API Key format');
        return false;
    }
    
    try {
        instance = new GeminiCabinetService(apiKey);
        console.log('✓ Gemini service initialized successfully');
        return true;
    } catch (error) {
        console.error('❌ Failed to initialize Gemini service:', error);
        return false;
    }
};

export const getGeminiService = (): GeminiCabinetService => { 
    if (!instance) throw new Error("AI Service not initialized. Check API Key in environment variables."); 
    return instance; 
};

export const generateCabinetConfig = async (prompt: string, materials: Material[]) => {
    return getGeminiService().createDesignFromPrompt(prompt, materials);
}

export const askExpert = async (question: string): Promise<string> => {
    return getGeminiService().askFurnitureExpert(question);
};

export const askExpertStreaming = async (
  question: string,
  onChunk?: (chunk: string) => void
): Promise<string> => {
    return getGeminiService().askFurnitureExpertStreaming(question, onChunk);
};

export const getAIMetrics = () => {
    return getGeminiService().getMetrics();
};

export const resetAIMetrics = () => {
    return getGeminiService().resetMetrics();
};

export const analyzeProject = async (data: ProjectAnalysisData): Promise<string> => {
    return getGeminiService().conductTechnicalAudit(data);
};

export const autoPlaceHardware = (panels: Panel[], type: ConnectionType = 'confirmat'): Panel[] => {
    if (instance) return instance.autoPlaceHardware(panels, type);
    // Fallback if AI service isn't init (since hardware calc is local logic)
    return new GeminiCabinetService("dummy").autoPlaceHardware(panels, type);
};

export const optimizeCutList = analyzeProject;
