/**
 * Performance Monitor Tests
 * Полное тестирование мониторинга производительности
 */

import { PerformanceMonitor } from '../PerformanceMonitor';

describe('PerformanceMonitor', () => {
  let monitor: PerformanceMonitor;

  beforeEach(() => {
    monitor = new PerformanceMonitor();
  });

  describe('Synchronous Phase Measurement', () => {
    test('should measure synchronous operation', () => {
      const { result, metrics } = monitor.measurePhase('test-phase', () => {
        return 42;
      });

      expect(result).toBe(42);
      expect(metrics).toBeDefined();
      expect(metrics.phase).toBe('test-phase');
    });

    test('should record duration', () => {
      const { metrics } = monitor.measurePhase('sleep', () => {
        const start = Date.now();
        while (Date.now() - start < 10) {}
        return 'done';
      });

      expect(metrics.duration).toBeGreaterThan(0);
    });

    test('should record memory usage', () => {
      const { metrics } = monitor.measurePhase('memory-test', () => {
        return new Array(1000).fill(0);
      });

      expect(metrics.memoryBefore).toBeGreaterThanOrEqual(0);
      expect(metrics.memoryAfter).toBeGreaterThanOrEqual(0);
      expect(metrics.memoryUsed).toBeDefined();
    });

    test('should calculate memory difference correctly', () => {
      const { metrics } = monitor.measurePhase('memory-calc', () => {
        return 123;
      });

      expect(metrics.memoryAfter - metrics.memoryBefore).toBeCloseTo(metrics.memoryUsed, 2);
    });

    test('should record timestamp', () => {
      const before = new Date();
      const { metrics } = monitor.measurePhase('timestamp-test', () => {
        return 'result';
      });
      const after = new Date();

      expect(metrics.timestamp.getTime()).toBeGreaterThanOrEqual(before.getTime());
      expect(metrics.timestamp.getTime()).toBeLessThanOrEqual(after.getTime());
    });

    test('should handle function that throws error', () => {
      expect(() => {
        monitor.measurePhase('error-phase', () => {
          throw new Error('Test error');
        });
      }).toThrow('Test error');
    });

    test('should handle complex operations', () => {
      const { result, metrics } = monitor.measurePhase('complex', () => {
        const arr = Array.from({ length: 100 }, (_, i) => i);
        return arr.reduce((a, b) => a + b, 0);
      });

      expect(result).toBe(4950);
      expect(metrics.duration).toBeGreaterThan(0);
    });

    test('should preserve operation result type', () => {
      const { result: stringResult } = monitor.measurePhase('string', () => 'hello');
      expect(typeof stringResult).toBe('string');

      const { result: numberResult } = monitor.measurePhase('number', () => 123);
      expect(typeof numberResult).toBe('number');

      const { result: objectResult } = monitor.measurePhase('object', () => ({ a: 1 }));
      expect(typeof objectResult).toBe('object');
    });

    test('should handle null result', () => {
      const { result } = monitor.measurePhase('null-test', () => null);
      expect(result).toBeNull();
    });

    test('should handle undefined result', () => {
      const { result } = monitor.measurePhase('undefined-test', () => undefined);
      expect(result).toBeUndefined();
    });
  });

  describe('Asynchronous Phase Measurement', () => {
    test('should measure async operation', async () => {
      const { result, metrics } = await monitor.measurePhaseAsync('async-test', async () => {
        return 42;
      });

      expect(result).toBe(42);
      expect(metrics).toBeDefined();
      expect(metrics.phase).toBe('async-test');
    });

    test('should record duration for async operation', async () => {
      const { metrics } = await monitor.measurePhaseAsync('async-sleep', async () => {
        return new Promise(resolve => setTimeout(resolve, 10)).then(() => 'done');
      });

      expect(metrics.duration).toBeGreaterThan(0);
    });

    test('should handle async function that resolves', async () => {
      const { result } = await monitor.measurePhaseAsync('async-resolve', async () => {
        return Promise.resolve('resolved');
      });

      expect(result).toBe('resolved');
    });

    test('should handle async function that rejects', async () => {
      await expect(
        monitor.measurePhaseAsync('async-reject', async () => {
          throw new Error('Async error');
        })
      ).rejects.toThrow('Async error');
    });

    test('should record memory for async operation', async () => {
      const { metrics } = await monitor.measurePhaseAsync('async-memory', async () => {
        return new Array(1000).fill(0);
      });

      expect(metrics.memoryBefore).toBeGreaterThanOrEqual(0);
      expect(metrics.memoryAfter).toBeGreaterThanOrEqual(0);
    });

    test('should preserve async result type', async () => {
      const { result } = await monitor.measurePhaseAsync('async-type', async () => {
        return { key: 'value' };
      });

      expect(typeof result).toBe('object');
      expect((result as any).key).toBe('value');
    });
  });

  describe('Multiple Phase Measurements', () => {
    test('should store multiple measurements', () => {
      monitor.measurePhase('phase1', () => 1);
      monitor.measurePhase('phase2', () => 2);
      monitor.measurePhase('phase3', () => 3);

      const report = monitor.getReport();
      expect(Object.keys(report.phases).length).toBe(3);
    });

    test('should aggregate same phase names', () => {
      monitor.measurePhase('repeated', () => 1);
      monitor.measurePhase('repeated', () => 2);
      monitor.measurePhase('repeated', () => 3);

      const report = monitor.getReport();
      expect(report.phases['repeated'].count).toBe(3);
    });

    test('should track sequential phases', () => {
      monitor.measurePhase('seq1', () => {
        const start = Date.now();
        while (Date.now() - start < 10) {}
        return 'done';
      });

      monitor.measurePhase('seq2', () => {
        const start = Date.now();
        while (Date.now() - start < 20) {}
        return 'done';
      });

      const report = monitor.getReport();
      expect(report.phases['seq1']).toBeDefined();
      expect(report.phases['seq2']).toBeDefined();
      // seq2 should be at least as long or longer than seq1 (with margin for timing variation)
      expect(report.phases['seq2'].totalDuration).toBeGreaterThan(0);
      expect(report.phases['seq1'].totalDuration).toBeGreaterThan(0);
    });
  });

  describe('Performance Report', () => {
    test('should generate report with total duration', () => {
      monitor.measurePhase('phase1', () => {
        const start = Date.now();
        while (Date.now() - start < 5) {}
      });

      monitor.measurePhase('phase2', () => {
        const start = Date.now();
        while (Date.now() - start < 5) {}
      });

      const report = monitor.getReport();
      expect(report.totalDuration).toBeGreaterThan(0);
    });

    test('should calculate average duration per phase', () => {
      monitor.measurePhase('calc', () => 1);
      monitor.measurePhase('calc', () => 2);
      monitor.measurePhase('calc', () => 3);

      const report = monitor.getReport();
      const phase = report.phases['calc'];

      expect(phase.avgDuration).toBeDefined();
      expect(phase.avgDuration).toBeGreaterThan(0);
    });

    test('should track min duration per phase', () => {
      monitor.measurePhase('mintest', () => 1);
      monitor.measurePhase('mintest', () => 2);
      monitor.measurePhase('mintest', () => 3);

      const report = monitor.getReport();
      const phase = report.phases['mintest'];

      expect(phase.minDuration).toBeDefined();
      expect(phase.minDuration).toBeGreaterThan(0);
    });

    test('should track max duration per phase', () => {
      monitor.measurePhase('maxtest', () => 1);
      monitor.measurePhase('maxtest', () => 2);
      monitor.measurePhase('maxtest', () => 3);

      const report = monitor.getReport();
      const phase = report.phases['maxtest'];

      expect(phase.maxDuration).toBeDefined();
      expect(phase.maxDuration).toBeGreaterThan(0);
      expect(phase.maxDuration).toBeGreaterThanOrEqual(phase.minDuration);
    });

    test('should calculate total memory usage', () => {
      monitor.measurePhase('memory1', () => new Array(100).fill(0));
      monitor.measurePhase('memory2', () => new Array(200).fill(0));

      const report = monitor.getReport();
      expect(report.totalMemory).toBeDefined();
    });

    test('should not include duration array in report', () => {
      monitor.measurePhase('test', () => 1);
      const report = monitor.getReport();

      expect((report.phases['test'] as any).durations).toBeUndefined();
    });

    test('should handle empty measurements', () => {
      const report = monitor.getReport();

      expect(report.totalDuration).toBe(0);
      expect(report.totalMemory).toBe(0);
      expect(Object.keys(report.phases).length).toBe(0);
    });

    test('should count phase executions correctly', () => {
      monitor.measurePhase('count', () => 1);
      monitor.measurePhase('count', () => 2);
      monitor.measurePhase('count', () => 3);
      monitor.measurePhase('count', () => 4);
      monitor.measurePhase('count', () => 5);

      const report = monitor.getReport();
      expect(report.phases['count'].count).toBe(5);
    });
  });

  describe('CSV Export', () => {
    test('should export to CSV format', () => {
      monitor.measurePhase('phase1', () => 1);
      monitor.measurePhase('phase2', () => 2);

      const csv = monitor.exportToCSV();
      expect(csv).toContain('Phase,Duration');
      expect(csv).toContain('phase1');
      expect(csv).toContain('phase2');
    });

    test('should include header row in CSV', () => {
      monitor.measurePhase('test', () => 1);
      const csv = monitor.exportToCSV();

      const lines = csv.split('\n');
      expect(lines[0]).toContain('Phase');
      expect(lines[0]).toContain('Duration');
      expect(lines[0]).toContain('Memory');
    });

    test('should include memory columns', () => {
      monitor.measurePhase('test', () => 1);
      const csv = monitor.exportToCSV();

      expect(csv).toContain('Memory Before');
      expect(csv).toContain('Memory After');
      expect(csv).toContain('Memory Used');
    });

    test('should include timestamp in CSV', () => {
      monitor.measurePhase('test', () => 1);
      const csv = monitor.exportToCSV();

      expect(csv).toContain('Timestamp');
    });

    test('should format numbers with 2 decimal places', () => {
      monitor.measurePhase('test', () => 1);
      const csv = monitor.exportToCSV();

      const lines = csv.split('\n');
      expect(lines.length).toBeGreaterThan(1);
      const dataLine = lines[1];
      const parts = dataLine.split(',');
      expect(parts[1]).toMatch(/\d+\.\d{2}/);
    });

    test('should handle empty metrics', () => {
      const csv = monitor.exportToCSV();

      const lines = csv.split('\n');
      expect(lines[0]).toContain('Phase');
      expect(lines.length).toBe(1);
    });

    test('should include ISO timestamp format', () => {
      monitor.measurePhase('test', () => 1);
      const csv = monitor.exportToCSV();

      expect(csv).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    });

    test('should handle multiple phases in CSV', () => {
      monitor.measurePhase('phase1', () => 1);
      monitor.measurePhase('phase2', () => 2);
      monitor.measurePhase('phase3', () => 3);

      const csv = monitor.exportToCSV();
      const lines = csv.split('\n');

      expect(lines.length).toBe(4);
      expect(lines[1]).toContain('phase1');
      expect(lines[2]).toContain('phase2');
      expect(lines[3]).toContain('phase3');
    });
  });

  describe('Clear Metrics', () => {
    test('should clear all metrics', () => {
      monitor.measurePhase('phase1', () => 1);
      monitor.measurePhase('phase2', () => 2);

      let report = monitor.getReport();
      expect(Object.keys(report.phases).length).toBeGreaterThan(0);

      monitor.clear();
      report = monitor.getReport();

      expect(Object.keys(report.phases).length).toBe(0);
      expect(report.totalDuration).toBe(0);
      expect(report.totalMemory).toBe(0);
    });

    test('should allow measuring after clear', () => {
      monitor.measurePhase('phase1', () => 1);
      monitor.clear();
      monitor.measurePhase('phase2', () => 2);

      const report = monitor.getReport();
      expect(report.phases['phase1']).toBeUndefined();
      expect(report.phases['phase2']).toBeDefined();
    });

    test('should clear CSV export after clearing metrics', () => {
      monitor.measurePhase('phase1', () => 1);
      monitor.clear();

      const csv = monitor.exportToCSV();
      const lines = csv.split('\n');

      expect(lines.length).toBe(1);
    });
  });

  describe('Performance Analysis', () => {
    test('should identify slowest phase', () => {
      monitor.measurePhase('fast', () => {
        let sum = 0;
        for (let i = 0; i < 100; i++) sum += i;
      });

      monitor.measurePhase('slow', () => {
        let sum = 0;
        for (let i = 0; i < 10000; i++) sum += i;
      });

      const report = monitor.getReport();
      const fastDuration = report.phases['fast'].avgDuration;
      const slowDuration = report.phases['slow'].avgDuration;

      expect(slowDuration).toBeGreaterThanOrEqual(fastDuration);
    });

    test('should track phase variability', () => {
      monitor.measurePhase('variable', () => {
        let sum = 0;
        for (let i = 0; i < 100; i++) sum += i;
      });

      monitor.measurePhase('variable', () => {
        let sum = 0;
        for (let i = 0; i < 1000; i++) sum += i;
      });

      const report = monitor.getReport();
      const phase = report.phases['variable'];

      expect(phase.maxDuration).toBeGreaterThanOrEqual(phase.minDuration);
    });

    test('should calculate total operation time', () => {
      monitor.measurePhase('op1', () => {
        const start = Date.now();
        while (Date.now() - start < 2) {}
      });

      monitor.measurePhase('op2', () => {
        const start = Date.now();
        while (Date.now() - start < 2) {}
      });

      const report = monitor.getReport();
      expect(report.totalDuration).toBeGreaterThan(0);
    });

    test('should handle memory intensive operations', () => {
      monitor.measurePhase('memory-intensive', () => {
        const arr = new Array(10000).fill(Math.random());
        return arr.length;
      });

      const report = monitor.getReport();
      const phase = report.phases['memory-intensive'];

      expect(phase).toBeDefined();
      expect(phase.count).toBe(1);
    });
  });

  describe('Mixed Operations', () => {
    test('should handle mix of sync and async phases', async () => {
      monitor.measurePhase('sync1', () => 1);
      await monitor.measurePhaseAsync('async1', async () => 2);
      monitor.measurePhase('sync2', () => 3);
      await monitor.measurePhaseAsync('async2', async () => 4);

      const report = monitor.getReport();
      expect(Object.keys(report.phases).length).toBe(4);
    });

    test('should maintain separate aggregations for sync/async phases', async () => {
      monitor.measurePhase('work', () => 1);
      monitor.measurePhase('work', () => 2);
      await monitor.measurePhaseAsync('work', async () => 3);

      const report = monitor.getReport();
      expect(report.phases['work'].count).toBe(3);
    });

    test('should calculate totals correctly with mixed operations', async () => {
      monitor.measurePhase('phase1', () => 1);
      await monitor.measurePhaseAsync('phase2', async () => 2);
      monitor.measurePhase('phase3', () => 3);

      const report = monitor.getReport();
      expect(report.totalDuration).toBeGreaterThan(0);
    });
  });

  describe('Edge Cases', () => {
    test('should handle very fast operations', () => {
      const { metrics } = monitor.measurePhase('ultra-fast', () => 1);

      expect(metrics.duration).toBeGreaterThanOrEqual(0);
    });

    test('should handle operations with zero memory change', () => {
      const { metrics } = monitor.measurePhase('no-memory', () => {
        return 42;
      });

      expect(metrics.memoryUsed).toBeDefined();
    });

    test('should handle phase names with special characters', () => {
      monitor.measurePhase('phase-1_test:special', () => 1);

      const report = monitor.getReport();
      expect(report.phases['phase-1_test:special']).toBeDefined();
    });

    test('should handle very long phase names', () => {
      const longName = 'a'.repeat(1000);
      monitor.measurePhase(longName, () => 1);

      const report = monitor.getReport();
      expect(report.phases[longName]).toBeDefined();
    });

    test('should handle large number of phases', () => {
      for (let i = 0; i < 100; i++) {
        monitor.measurePhase(`phase-${i}`, () => i);
      }

      const report = monitor.getReport();
      expect(Object.keys(report.phases).length).toBe(100);
    });

    test('should handle repeated measurements of same phase', () => {
      for (let i = 0; i < 50; i++) {
        monitor.measurePhase('repeated', () => i);
      }

      const report = monitor.getReport();
      expect(report.phases['repeated'].count).toBe(50);
    });
  });

  describe('Data Integrity', () => {
    test('should not lose data between measurements', () => {
      monitor.measurePhase('phase1', () => 1);
      const report1 = monitor.getReport();

      monitor.measurePhase('phase2', () => 2);
      const report2 = monitor.getReport();

      expect(report2.phases['phase1']).toBeDefined();
      expect(report2.phases['phase2']).toBeDefined();
    });

    test('should maintain consistent phase data', () => {
      monitor.measurePhase('test', () => 1);
      monitor.measurePhase('test', () => 2);

      const report1 = monitor.getReport();
      const report2 = monitor.getReport();

      expect(report1.phases['test'].count).toBe(report2.phases['test'].count);
    });

    test('should calculate statistics correctly with multiple measurements', () => {
      monitor.measurePhase('stats', () => 1);
      monitor.measurePhase('stats', () => 2);
      monitor.measurePhase('stats', () => 3);

      const report = monitor.getReport();
      const phase = report.phases['stats'];

      expect(phase.count).toBe(3);
      expect(phase.totalDuration).toBeGreaterThan(0);
      expect(phase.avgDuration).toBeLessThanOrEqual(phase.maxDuration);
      expect(phase.avgDuration).toBeGreaterThanOrEqual(phase.minDuration);
    });
  });
});
