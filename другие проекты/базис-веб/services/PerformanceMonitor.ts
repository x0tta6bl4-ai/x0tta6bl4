/**
 * ФАЗА 8: Performance Monitor
 * Мониторинг производительности и сбор метрик
 */

import { PerformanceMetrics, PerformanceReport } from '../types/CADTypes';

/**
 * Монитор производительности
 */
export class PerformanceMonitor {
  private metrics: PerformanceMetrics[] = [];
  
  /**
   * Измерить время выполнения синхронной операции
   * @param phaseName Название операции
   * @param operation Функция для выполнения
   * @returns Результат операции и метрики
   */
  public measurePhase<T>(
    phaseName: string,
    operation: () => T
  ): { result: T; metrics: PerformanceMetrics } {
    const memBefore = this.getHeapUsed();
    const startTime = performance.now();
    
    const result = operation();
    
    const duration = performance.now() - startTime;
    const memAfter = this.getHeapUsed();
    
    const metrics: PerformanceMetrics = {
      phase: phaseName,
      duration,
      memoryBefore: memBefore,
      memoryAfter: memAfter,
      memoryUsed: memAfter - memBefore,
      timestamp: new Date()
    };
    
    this.metrics.push(metrics);
    
    return { result, metrics };
  }
  
  /**
   * Измерить время выполнения асинхронной операции
   */
  public async measurePhaseAsync<T>(
    phaseName: string,
    operation: () => Promise<T>
  ): Promise<{ result: T; metrics: PerformanceMetrics }> {
    const memBefore = this.getHeapUsed();
    const startTime = performance.now();
    
    const result = await operation();
    
    const duration = performance.now() - startTime;
    const memAfter = this.getHeapUsed();
    
    const metrics: PerformanceMetrics = {
      phase: phaseName,
      duration,
      memoryBefore: memBefore,
      memoryAfter: memAfter,
      memoryUsed: memAfter - memBefore,
      timestamp: new Date()
    };
    
    this.metrics.push(metrics);
    
    return { result, metrics };
  }
  
  /**
   * Получить итоговый отчёт производительности
   */
  public getReport(): PerformanceReport {
    const totalDuration = this.metrics.reduce((sum, m) => sum + m.duration, 0);
    const totalMemory = this.metrics.reduce((sum, m) => sum + m.memoryUsed, 0);
    
    const phases: Record<string, any> = {};
    
    this.metrics.forEach(m => {
      if (!phases[m.phase]) {
        phases[m.phase] = {
          count: 0,
          totalDuration: 0,
          durations: []
        };
      }
      phases[m.phase].count++;
      phases[m.phase].totalDuration += m.duration;
      phases[m.phase].durations.push(m.duration);
    });
    
    // Вычислить статистику для каждой фазы
    Object.keys(phases).forEach(phase => {
      const p = phases[phase];
      p.avgDuration = p.totalDuration / p.count;
      p.minDuration = Math.min(...p.durations);
      p.maxDuration = Math.max(...p.durations);
      delete p.durations;
    });
    
    return { totalDuration, totalMemory, phases };
  }
  
  /**
   * Экспортировать метрики в CSV
   */
  public exportToCSV(): string {
    const header = 'Phase,Duration (ms),Memory Before (MB),Memory After (MB),Memory Used (MB),Timestamp';
    const rows = this.metrics.map(m =>
      `${m.phase},${m.duration.toFixed(2)},${m.memoryBefore.toFixed(2)},${m.memoryAfter.toFixed(2)},${m.memoryUsed.toFixed(2)},${m.timestamp.toISOString()}`
    ).join('\n');
    
    return rows.length > 0 ? header + '\n' + rows : header;
  }
  
  /**
   * Очистить метрики
   */
  public clear(): void {
    this.metrics = [];
  }
  
  /**
   * Получить текущее использование памяти (МБ)
   */
  private getHeapUsed(): number {
    if (typeof process !== 'undefined' && process.memoryUsage) {
      return process.memoryUsage().heapUsed / 1024 / 1024;
    }
    if (typeof performance !== 'undefined' && (performance as any).memory) {
      return (performance as any).memory.usedJSHeapSize / 1024 / 1024;
    }
    return 0;
  }
}
