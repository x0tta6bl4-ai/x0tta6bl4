/**
 * Performance Optimization Utilities - Phase 3
 * Helps identify and fix re-render issues
 */

import { useRef, useEffect, useState, type DependencyList } from 'react';
import { PerformanceMonitor3D, PerformanceMetrics } from '../services/PerformanceMonitor3D';

interface RenderMetrics {
  componentName: string;
  renderCount: number;
  lastRenderTime: number;
  totalRenderTime: number;
  averageRenderTime: number;
}

/**
 * useRenderTracker - Track component render count and timing
 * 
 * Usage:
 * ```tsx
 * function MyComponent() {
 *   useRenderTracker('MyComponent');
 *   return <div>Component</div>;
 * }
 * ```
 */
export function useRenderTracker(componentName: string) {
  const renderCount = useRef(0);
  const renderTimes = useRef<number[]>([]);
  const startTime = useRef(performance.now());

  useEffect(() => {
    const renderTime = performance.now() - startTime.current;
    renderCount.current++;
    renderTimes.current.push(renderTime);

    const metrics: RenderMetrics = {
      componentName,
      renderCount: renderCount.current,
      lastRenderTime: renderTime,
      totalRenderTime: renderTimes.current.reduce((a, b) => a + b, 0),
      averageRenderTime: renderTimes.current.reduce((a, b) => a + b, 0) / renderTimes.current.length,
    };

    if (process.env.NODE_ENV === 'development') {
      console.log(`[${componentName}] Render #${metrics.renderCount}`, {
        lastRender: `${metrics.lastRenderTime.toFixed(2)}ms`,
        average: `${metrics.averageRenderTime.toFixed(2)}ms`,
        total: `${metrics.totalRenderTime.toFixed(2)}ms`,
      });
    }

    startTime.current = performance.now();
  });
}

/**
 * usePrevious - Keep track of previous value for comparison
 * 
 * Usage:
 * ```tsx
 * const prevValue = usePrevious(value);
 * useEffect(() => {
 *   if (prevValue !== value) {
 *     console.log('Value changed!');
 *   }
 * }, [value, prevValue]);
 * ```
 */
export function usePrevious<T>(value: T, initialValue?: T): T | undefined {
  const ref = useRef<T | undefined>(initialValue);

  useEffect(() => {
    ref.current = value;
  }, [value]);

  return ref.current;
}

/**
 * useWhyDidYouUpdate - Log which props changed causing re-render
 * 
 * Usage:
 * ```tsx
 * interface MyProps {
 *   name: string;
 *   count: number;
 * }
 * 
 * function MyComponent(props: MyProps) {
 *   useWhyDidYouUpdate('MyComponent', props);
 *   return <div>{props.name}: {props.count}</div>;
 * }
 * ```
 */
export function useWhyDidYouUpdate(componentName: string, props: Record<string, unknown>) {
  const previousProps = useRef<Record<string, unknown> | undefined>(undefined);

  useEffect(() => {
    if (previousProps.current) {
      const allKeys = Object.keys({ ...previousProps.current, ...props });
      const changedProps: Record<string, { from: unknown; to: unknown }> = {};

      allKeys.forEach((key) => {
        if (previousProps.current?.[key] !== props[key]) {
          changedProps[key] = {
            from: previousProps.current?.[key],
            to: props[key],
          };
        }
      });

      if (Object.keys(changedProps).length > 0) {
        if (process.env.NODE_ENV === 'development') {
          console.log(`[${componentName}] Props changed:`, changedProps);
        }
      }
    }

    previousProps.current = props;
  }, [props, componentName]);
}

/**
 * Performance monitoring helper for async operations
 * 
 * Usage:
 * ```tsx
 * const { measure, results } = usePerformanceMonitor();
 * 
 * const handleClick = async () => {
 *   const timer = measure('fetchData');
 *   const data = await fetch(...);
 *   timer.end();
 * };
 * ```
 */
/**
 * use3DPerformanceMonitor - Track 3D rendering performance metrics
 * Returns real-time metrics including FPS, GPU memory, CPU usage, frame time, draw calls, and triangle count
 * 
 * Usage:
 * ```tsx
 * const metrics = use3DPerformanceMonitor();
 * console.log('FPS:', metrics.fps);
 * ```
 */
export function use3DPerformanceMonitor(updateInterval: number = 1000): PerformanceMetrics {
  const [metrics, setMetrics] = useState<PerformanceMetrics>({
    fps: 0,
    gpuMemory: 0,
    cpuUsage: 0,
    frameTime: 0,
    drawCalls: 0,
    triangleCount: 0,
    renderTime: 0
  });

  const monitorRef = useRef<PerformanceMonitor3D | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    monitorRef.current = new PerformanceMonitor3D();
    monitorRef.current.start();

    intervalRef.current = setInterval(() => {
      if (monitorRef.current) {
        const newMetrics = monitorRef.current.update();
        setMetrics(newMetrics);
      }
    }, updateInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (monitorRef.current) {
        monitorRef.current.stop();
      }
    };
  }, [updateInterval]);

  return metrics;
}

/**
 * usePerformanceMonitor - Track general performance for async operations
 * 
 * Usage:
 * ```tsx
 * const { measure, results } = usePerformanceMonitor();
 * 
 * const handleClick = async () => {
 *   const timer = measure('fetchData');
 *   const data = await fetch(...);
 *   timer.end();
 * };
 * ```
 */
export function usePerformanceMonitor() {
  const timers = useRef<Map<string, number>>(new Map());
  const results = useRef<Map<string, number[]>>(new Map());

  return {
    measure: (label: string) => {
      const startTime = performance.now();
      return {
        end: () => {
          const endTime = performance.now();
          const duration = endTime - startTime;

          if (!results.current.has(label)) {
            results.current.set(label, []);
          }
          results.current.get(label)!.push(duration);

          if (process.env.NODE_ENV === 'development') {
            console.log(`[Performance] ${label}: ${duration.toFixed(2)}ms`);
          }

          return duration;
        },
      };
    },
    getResults: () => {
      const output: Record<string, { count: number; total: number; average: number }> = {};
      results.current.forEach((times, label) => {
        output[label] = {
          count: times.length,
          total: times.reduce((a, b) => a + b, 0),
          average: times.reduce((a, b) => a + b, 0) / times.length,
        };
      });
      return output;
    },
  };
}

/**
 * useCallbackWithDeps - useCallback with dependency tracking
 * Warns if callback changes unnecessarily
 * 
 * Usage:
 * ```tsx
 * const memoizedCallback = useCallbackWithDeps(
 *   () => { handleClick(); },
 *   [handleClick],
 *   'onClick'
 * );
 * ```
 */
export function useCallbackWithDeps<T extends (...args: unknown[]) => unknown>(
  callback: T,
  deps: DependencyList,
  label?: string
): T {
  const prevDeps = useRef<DependencyList | undefined>(undefined);
  const prevCallback = useRef<T | undefined>(undefined);

  const depsChanged = !prevDeps.current || prevDeps.current.some((dep, i) => dep !== deps[i]);

  if (depsChanged) {
    prevCallback.current = callback;
    prevDeps.current = deps;

    if (label && process.env.NODE_ENV === 'development') {
      console.log(`[useCallbackWithDeps] ${label} regenerated`);
    }
  }

  return prevCallback.current || callback;
}

/**
 * Batch multiple state updates into single re-render
 * Useful for complex state changes
 * 
 * Usage:
 * ```tsx
 * const batchUpdates = useBatchUpdates();
 * 
 * const handleComplexUpdate = () => {
 *   batchUpdates(() => {
 *     setState1(newValue1);
 *     setState2(newValue2);
 *     setState3(newValue3);
 *   });
 * };
 * ```
 */
export function useBatchUpdates() {
  return (updates: () => void) => {
    // In React 18+, use flushSync if needed
    if ('flushSync' in require('react-dom')) {
      const { flushSync } = require('react-dom');
      flushSync(updates);
    } else {
      updates();
    }
  };
}

/**
 * useDebounce - Debounce value changes
 * Useful for search inputs, resize handlers, etc.
 * 
 * Usage:
 * ```tsx
 * const [searchTerm, setSearchTerm] = useState('');
 * const debouncedSearchTerm = useDebounce(searchTerm, 300);
 * 
 * useEffect(() => {
 *   console.log('Search:', debouncedSearchTerm);
 * }, [debouncedSearchTerm]);
 * ```
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}

/**
 * useThrottle - Throttle function calls
 * Limits how often a function can be called
 * 
 * Usage:
 * ```tsx
 * const throttledScroll = useThrottle(() => {
 *   console.log('Scrolling...');
 * }, 100);
 * 
 * window.addEventListener('scroll', throttledScroll);
 * ```
 */
export function useThrottle<T extends (...args: unknown[]) => unknown>(
  callback: T,
  limit: number
): T {
  const inThrottle = useRef(false);

  return ((...args: unknown[]) => {
    if (!inThrottle.current) {
      callback(...args);
      inThrottle.current = true;
      setTimeout(() => {
        inThrottle.current = false;
      }, limit);
    }
  }) as T;
}

/**
 * List virtualization helper for large lists
 * Returns visible items based on scroll position
 */
export function useVirtualization(
  items: unknown[],
  itemHeight: number,
  containerHeight: number,
  scrollTop: number
) {
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - 1);
  const endIndex = Math.min(
    items.length,
    Math.ceil((scrollTop + containerHeight) / itemHeight) + 1
  );

  return {
    visibleItems: items.slice(startIndex, endIndex),
    startIndex,
    endIndex,
    offsetY: startIndex * itemHeight,
  };
}
