import { useEffect, useRef, useState } from 'react';

export interface PerformanceMetrics {
  fps: number;
  gpuMemory: number;
  cpuUsage: number;
  frameTime: number;
  drawCalls: number;
  triangleCount: number;
  renderTime: number;
}

export interface PerformanceStats {
  average: number;
  min: number;
  max: number;
  samples: number[];
}

export class PerformanceMonitor3D {
  private startTime: number;
  private frameCount: number;
  private lastTime: number;
  private frameTimes: number[];
  private fpsHistory: number[];
  private maxSamples: number;
  private running: boolean;

  constructor(maxSamples: number = 60) {
    this.startTime = performance.now();
    this.frameCount = 0;
    this.lastTime = performance.now();
    this.frameTimes = [];
    this.fpsHistory = [];
    this.maxSamples = maxSamples;
    this.running = false;
  }

  start(): void {
    this.running = true;
    this.startTime = performance.now();
    this.frameCount = 0;
    this.lastTime = performance.now();
    this.frameTimes = [];
    this.fpsHistory = [];
  }

  stop(): void {
    this.running = false;
  }

  update(): PerformanceMetrics {
    if (!this.running) {
      return {
        fps: 0,
        gpuMemory: 0,
        cpuUsage: 0,
        frameTime: 0,
        drawCalls: 0,
        triangleCount: 0,
        renderTime: 0
      };
    }

    const now = performance.now();
    const deltaTime = now - this.lastTime;
    this.lastTime = now;

    // Calculate FPS
    this.frameCount++;
    const elapsed = now - this.startTime;
    const fps = Math.round((this.frameCount / elapsed) * 1000);

    // Store frame time
    this.frameTimes.push(deltaTime);
    if (this.frameTimes.length > this.maxSamples) {
      this.frameTimes.shift();
    }

    // Store FPS history
    this.fpsHistory.push(fps);
    if (this.fpsHistory.length > this.maxSamples) {
      this.fpsHistory.shift();
    }

    // Calculate frame time statistics
    const avgFrameTime = this.frameTimes.reduce((sum, time) => sum + time, 0) / this.frameTimes.length;

    return {
      fps,
      gpuMemory: this.getGPUMemory(),
      cpuUsage: this.getCPUUsage(),
      frameTime: avgFrameTime,
      drawCalls: 0, // Not available in standard Web API
      triangleCount: 0, // Not available in standard Web API
      renderTime: avgFrameTime * 0.7, // Estimated
    };
  }

  private getGPUMemory(): number {
    // This is an approximation since Web API doesn't provide direct GPU memory info
    // We could use WebGL extensions if available
    return 0;
  }

  private getCPUUsage(): number {
    // This is a rough estimate since Web API doesn't provide direct CPU usage
    return 0;
  }

  getStats(): {
    fps: PerformanceStats;
    frameTime: PerformanceStats;
  } {
    return {
      fps: this.calculateStats(this.fpsHistory),
      frameTime: this.calculateStats(this.frameTimes),
    };
  }

  private calculateStats(samples: number[]): PerformanceStats {
    if (samples.length === 0) {
      return {
        average: 0,
        min: 0,
        max: 0,
        samples: [],
      };
    }

    const sum = samples.reduce((a, b) => a + b, 0);
    const average = sum / samples.length;
    const min = Math.min(...samples);
    const max = Math.max(...samples);

    return {
      average,
      min,
      max,
      samples: [...samples],
    };
  }
}

export const usePerformanceMonitor = (updateInterval: number = 1000) => {
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
};

export const useFPSCounter = (): number => {
  const [fps, setFps] = useState(0);
  const frameCountRef = useRef(0);
  const lastTimeRef = useRef(performance.now());

  useEffect(() => {
    const updateFPS = () => {
      const now = performance.now();
      frameCountRef.current++;

      if (now - lastTimeRef.current >= 1000) {
        const newFPS = Math.round((frameCountRef.current * 1000) / (now - lastTimeRef.current));
        setFps(newFPS);
        frameCountRef.current = 0;
        lastTimeRef.current = now;
      }

      requestAnimationFrame(updateFPS);
    };

    const rafId = requestAnimationFrame(updateFPS);
    return () => cancelAnimationFrame(rafId);
  }, []);

  return fps;
};
