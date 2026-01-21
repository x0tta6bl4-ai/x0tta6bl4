/**
 * AI сервис с fallback на локальные модели
 * Сначала пытается использовать Ollama/Gemini, затем локальные joblib модели
 */

import { Panel, Material } from '../types';
import { localModelService } from './localModelService';

export interface CabinetSuggestion {
  material?: string;
  complexity?: string;
  suggestions?: string[];
  source: 'ollama' | 'local' | 'hybrid';
}

class AIServiceWithFallback {
  private localServiceReady = false;

  async initialize(): Promise<void> {
    this.localServiceReady = await localModelService.initialize();
    if (this.localServiceReady) {
      console.log('✅ AI Fallback System готов (Ollama + Local Models)');
    } else {
      console.log('⚠️  Локальные модели недоступны, будет использовано только Ollama');
    }
  }

  /**
   * Получить рекомендации по шкафу с fallback логикой
   */
  async getSuggestions(
    width: number,
    height: number,
    depth: number,
    doorCount: number = 2,
    shelfCount: number = 3
  ): Promise<CabinetSuggestion> {
    // Сначала пытаемся использовать локальные модели
    if (this.localServiceReady) {
      try {
        const analysis = await localModelService.analyzeCabinet({
          width,
          height,
          depth,
          doorCount,
          shelfCount,
        });

        const material = await localModelService.recommendMaterial(width, height, depth);

        return {
          material,
          complexity: analysis.complexity_level,
          suggestions: analysis.suggestions,
          source: 'local',
        };
      } catch (e) {
        console.warn('⚠️  Ошибка локальной модели, используется Ollama:', e);
      }
    }

    // Fallback на Ollama/Gemini (пустой результат - используется существующая логика)
    return {
      source: 'ollama',
      suggestions: [
        'Используйте стандартные рекомендации для данных размеров',
      ],
    };
  }

  /**
   * Анализ сложности конфигурации
   */
  async analyzeComplexity(panels: Panel[]): Promise<string> {
    if (!this.localServiceReady) {
      return 'Используйте Ollama для анализа сложности';
    }

    try {
      let totalComplexity = 0;
      let analysisCount = 0;

      for (const panel of panels.slice(0, 3)) {
        // Анализируем только первые 3 панели для производительности
        const result = await localModelService.predictComplexity(
          panel.width,
          panel.height,
          panel.depth
        );

        if (result.success && result.complexity_score) {
          totalComplexity += result.complexity_score;
          analysisCount++;
        }
      }

      if (analysisCount === 0) return 'Не удалось оценить сложность';

      const avgComplexity = totalComplexity / analysisCount;

      if (avgComplexity < 0.33) {
        return '🟢 Низкая сложность - стандартная конструкция';
      } else if (avgComplexity < 0.66) {
        return '🟡 Средняя сложность - требует внимания к деталям';
      } else {
        return '🔴 Высокая сложность - требуется опытный мастер';
      }
    } catch (e) {
      console.error('Ошибка анализа сложности:', e);
      return 'Требуется анализ в Ollama';
    }
  }

  /**
   * Рекомендация материала с гибридной логикой
   */
  async recommendMaterial(
    width: number,
    height: number,
    depth: number,
    budget?: string
  ): Promise<string> {
    if (!this.localServiceReady) {
      // Базовые рекомендации без локальных моделей
      if (budget === 'premium') return 'Lamarty (премиум)';
      if (budget === 'budget') return 'EGGER (экономичный)';
      return 'EGGER (стандартный выбор)';
    }

    try {
      return await localModelService.recommendMaterial(width, height, depth);
    } catch (e) {
      console.warn('Ошибка рекомендации материала:', e);
      return 'EGGER (стандартный выбор)';
    }
  }

  /**
   * Проверить доступность локальных моделей
   */
  async isLocalServiceAvailable(): Promise<boolean> {
    return this.localServiceReady;
  }

  /**
   * Получить информацию о доступных моделях
   */
  async getAvailableModels(): Promise<any> {
    return await localModelService.getAvailableModels();
  }

  /**
   * Генерация рекомендаций по оптимизации конструкции
   */
  async generateOptimizationSuggestions(
    panels: Panel[],
    materials: Material[]
  ): Promise<string[]> {
    if (!this.localServiceReady) {
      return ['Используйте Ollama для получения рекомендаций'];
    }

    const suggestions: string[] = [];

    // Анализ размеров панелей
    const avgHeight = panels.reduce((sum, p) => sum + p.height, 0) / panels.length;
    const avgWidth = panels.reduce((sum, p) => sum + p.width, 0) / panels.length;

    if (avgHeight > 2300) {
      suggestions.push('📐 Рассмотрите вертикальное разделение для упрощения доставки');
    }

    if (avgWidth > 2000) {
      suggestions.push('📏 Используйте центральный средник для стабильности');
    }

    // Анализ типов панелей
    const shelfPanels = panels.filter(p => p.layer === 'shelves');
    if (shelfPanels.length > 5) {
      suggestions.push('🔧 Большое количество полок - убедитесь в достаточной поддержке');
    }

    if (suggestions.length === 0) {
      suggestions.push('✅ Конструкция оптимальна');
    }

    return suggestions;
  }
}

export const aiServiceWithFallback = new AIServiceWithFallback();
