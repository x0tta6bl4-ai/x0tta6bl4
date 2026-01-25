/**
 * Сервис локальных ML моделей - Fallback для Ollama
 * Использует joblib модели из /x0tta6bl4_paradox_zone/
 */

export interface PredictionResult {
  success: boolean;
  [key: string]: any;
}

export interface CabinetAnalysis {
  cabinet_type?: string;
  complexity_score?: number;
  complexity_level?: 'low' | 'medium' | 'high';
  suggestions?: string[];
}

class LocalModelService {
  private readonly LOCAL_AI_URL = 'http://127.0.0.1:8001';
  private serviceAvailable = false;
  private initialized = false;

  async initialize(): Promise<boolean> {
    if (this.initialized) return this.serviceAvailable;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);

      const response = await fetch(`${this.LOCAL_AI_URL}/health`, {
        method: 'GET',
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      this.serviceAvailable = response.ok;
      this.initialized = true;
      console.log('✅ Local AI Service доступен');
      return true;
    } catch (e) {
      console.warn('⚠️  Local AI Service недоступен (используется Ollama)');
      this.initialized = true;
      return false;
    }
  }

  async isAvailable(): Promise<boolean> {
    if (!this.initialized) {
      return await this.initialize();
    }
    return this.serviceAvailable;
  }

  /**
   * Предсказание типа шкафа по размерам
   */
  async predictCabinetType(
    width: number,
    height: number,
    depth: number
  ): Promise<PredictionResult> {
    if (!await this.isAvailable()) {
      return { success: false, error: 'Service unavailable' };
    }

    try {
      const response = await fetch(
        `${this.LOCAL_AI_URL}/predict/cabinet-type`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model_name: 'demo_classifier',
            input_data: { width, height, depth },
          }),
        }
      );

      if (!response.ok) throw new Error('Prediction failed');
      return await response.json();
    } catch (e) {
      console.error('❌ Ошибка предсказания типа шкафа:', e);
      return { success: false, error: String(e) };
    }
  }

  /**
   * Предсказание сложности сборки
   */
  async predictComplexity(
    width: number,
    height: number,
    depth: number,
    doorCount: number = 2,
    shelfCount: number = 3
  ): Promise<PredictionResult> {
    if (!await this.isAvailable()) {
      return { success: false, error: 'Service unavailable' };
    }

    try {
      const response = await fetch(
        `${this.LOCAL_AI_URL}/predict/complexity`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model_name: 'demo_regressor',
            input_data: {
              width,
              height,
              depth,
              door_count: doorCount,
              shelf_count: shelfCount,
            },
          }),
        }
      );

      if (!response.ok) throw new Error('Complexity prediction failed');
      return await response.json();
    } catch (e) {
      console.error('❌ Ошибка предсказания сложности:', e);
      return { success: false, error: String(e) };
    }
  }

  /**
   * Анализ конфигурации шкафа
   */
  async analyzeCabinet(config: {
    width: number;
    height: number;
    depth: number;
    doorCount?: number;
    shelfCount?: number;
  }): Promise<CabinetAnalysis> {
    if (!await this.isAvailable()) {
      return { suggestions: ['Используйте Ollama для расширенного анализа'] };
    }

    try {
      const [typeResult, complexityResult] = await Promise.all([
        this.predictCabinetType(config.width, config.height, config.depth),
        this.predictComplexity(
          config.width,
          config.height,
          config.depth,
          config.doorCount,
          config.shelfCount
        ),
      ]);

      const suggestions: string[] = [];

      // Анализ результатов
      if (complexityResult.success && complexityResult.complexity_level === 'high') {
        suggestions.push('🔧 Рекомендуется использовать метабокс для выдвижных');
        suggestions.push('⚙️ Предусмотрите дополнительные укрепления');
      }

      if (config.width > 2000) {
        suggestions.push('📏 Рекомендуется центральный средник для широких шкафов');
      }

      if (config.height > 2300) {
        suggestions.push('📐 Рассмотрите разделение на две секции для доставки');
      }

      if (config.doorCount && config.doorCount > 3) {
        suggestions.push('🚪 Большое количество дверей - проверьте выравнивание');
      }

      return {
        cabinet_type: typeResult.cabinet_type,
        complexity_score: complexityResult.complexity_score,
        complexity_level: complexityResult.complexity_level,
        suggestions: suggestions.length > 0 ? suggestions : ['Конфигурация оптимальна'],
      };
    } catch (e) {
      console.error('❌ Ошибка анализа шкафа:', e);
      return { suggestions: ['Ошибка анализа'] };
    }
  }

  /**
   * Получить список доступных моделей
   */
  async getAvailableModels(): Promise<any> {
    if (!await this.isAvailable()) {
      return { models: [], total: 0 };
    }

    try {
      const response = await fetch(`${this.LOCAL_AI_URL}/models`);
      if (!response.ok) throw new Error('Failed to fetch models');
      return await response.json();
    } catch (e) {
      console.error('❌ Ошибка получения списка моделей:', e);
      return { models: [], total: 0 };
    }
  }

  /**
   * Сгенерировать рекомендацию по материалу на основе размеров
   */
  async recommendMaterial(
    width: number,
    height: number,
    depth: number
  ): Promise<string> {
    const complexity = await this.predictComplexity(width, height, depth);

    if (!complexity.success) return 'EGGER (рекомендуется по умолчанию)';

    if (complexity.complexity_level === 'high') {
      return 'Kronospan (повышенная стабильность)';
    }

    if (width > 1500 || height > 2000) {
      return 'Lamarty (эксклюзивный вариант)';
    }

    return 'EGGER (стандартный выбор)';
  }
}

export const localModelService = new LocalModelService();
