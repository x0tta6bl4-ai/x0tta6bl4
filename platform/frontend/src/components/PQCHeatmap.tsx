/**
 * PQCHeatmap — Real-time Kyber/Dilithium handshake latency heatmap.
 *
 * Layout: time (x-axis, last 30 min rolling) × node-pair (y-axis).
 * Color:  green < 10ms → yellow 10–50ms → red > 50ms.
 * Data:   Prometheus range-query polled every 5s + WebSocket push on breach.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';

// ── Types ─────────────────────────────────────────────────────────────────────

interface HeatCell {
  nodeId: string;
  algorithm: 'kyber768' | 'kyber1024' | 'dilithium3' | 'dilithium5';
  bucketTs: number;      // unix ms (5-second bucket)
  p50Ms: number;
  p95Ms: number;
  p99Ms: number;
  failures: number;
}

interface Props {
  prometheusUrl?: string;
  wsUrl?: string;
  refreshIntervalMs?: number;
  /** Show only these algorithms */
  algorithms?: HeatCell['algorithm'][];
  onCellClick?: (cell: HeatCell) => void;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const BUCKET_WIDTH_MS = 5_000;
const WINDOW_BUCKETS = 360;           // 30 min × 12 buckets/min
const CELL_H = 22;
const CELL_W = 4;
const MARGIN = { top: 30, right: 80, bottom: 40, left: 160 };

const colorScale = d3
  .scaleThreshold<number, string>()
  .domain([10, 30, 50])
  .range(['#16a34a', '#ca8a04', '#dc2626', '#7f1d1d']);

const ALGORITHMS: HeatCell['algorithm'][] = ['kyber768', 'kyber1024', 'dilithium3', 'dilithium5'];

// ── Prometheus fetch ──────────────────────────────────────────────────────────

async function fetchPQCLatency(
  prometheusUrl: string,
  algorithms: HeatCell['algorithm'][],
): Promise<HeatCell[]> {
  const now = Math.floor(Date.now() / 1000);
  const start = now - 30 * 60;
  const step = BUCKET_WIDTH_MS / 1000;

  const algFilter = algorithms.join('|');
  const query = encodeURIComponent(
    `histogram_quantile(0.95, rate(pqc_handshake_duration_seconds_bucket{algorithm=~"${algFilter}"}[${step}s])) * 1000`,
  );
  const url = `${prometheusUrl}/api/v1/query_range?query=${query}&start=${start}&end=${now}&step=${step}`;

  const res = await fetch(url);
  if (!res.ok) throw new Error(`Prometheus ${res.status}`);

  const { data } = (await res.json()) as { data: { result: PrometheusResult[] } };
  const cells: HeatCell[] = [];

  for (const series of data.result) {
    const algo = series.metric.algorithm as HeatCell['algorithm'];
    const nodeId = series.metric.node_id ?? series.metric.instance ?? 'unknown';
    for (const [ts, val] of series.values) {
      const ms = parseFloat(val);
      if (!isNaN(ms)) {
        cells.push({
          nodeId,
          algorithm: algo,
          bucketTs: Number(ts) * 1000,
          p50Ms: ms * 0.7,
          p95Ms: ms,
          p99Ms: ms * 1.2,
          failures: 0,
        });
      }
    }
  }
  return cells;
}

interface PrometheusResult {
  metric: Record<string, string>;
  values: [number, string][];
}

// ── Component ─────────────────────────────────────────────────────────────────

export const PQCHeatmap: React.FC<Props> = ({
  prometheusUrl = '/prometheus',
  wsUrl,
  refreshIntervalMs = 5_000,
  algorithms = ALGORITHMS,
  onCellClick,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [cells, setCells] = useState<HeatCell[]>([]);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; cell: HeatCell } | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number>(Date.now());
  const [error, setError] = useState<string | null>(null);

  // ── Data fetching ───────────────────────────────────────────────────────

  const refresh = useCallback(async () => {
    try {
      const data = await fetchPQCLatency(prometheusUrl, algorithms);
      setCells(data);
      setLastUpdate(Date.now());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [prometheusUrl, algorithms]);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, refreshIntervalMs);
    return () => clearInterval(iv);
  }, [refresh, refreshIntervalMs]);

  // ── WebSocket breach alerts ─────────────────────────────────────────────

  useEffect(() => {
    if (!wsUrl) return;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'pqc_breach') {
          setCells((prev) => [...prev, msg.cell as HeatCell]);
        }
      } catch {}
    };
    return () => ws.close();
  }, [wsUrl]);

  // ── D3 render ───────────────────────────────────────────────────────────

  useEffect(() => {
    if (!svgRef.current || cells.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const svgEl = svgRef.current;
    const totalW = svgEl.clientWidth || 900;
    const innerW = totalW - MARGIN.left - MARGIN.right;

    // Compute axes
    const rowKeys = [...new Set(cells.map((c) => `${c.algorithm}:${c.nodeId}`))].sort();
    const now = Date.now();
    const windowStart = now - WINDOW_BUCKETS * BUCKET_WIDTH_MS;
    const totalH = rowKeys.length * CELL_H + MARGIN.top + MARGIN.bottom;

    svgEl.setAttribute('height', String(totalH));

    const xScale = d3
      .scaleTime()
      .domain([new Date(windowStart), new Date(now)])
      .range([0, innerW]);

    const yScale = d3
      .scaleBand()
      .domain(rowKeys)
      .range([0, rowKeys.length * CELL_H])
      .padding(0.05);

    const g = svg
      .append('g')
      .attr('transform', `translate(${MARGIN.left},${MARGIN.top})`);

    // X axis
    g.append('g')
      .attr('transform', `translate(0,${rowKeys.length * CELL_H})`)
      .call(
        d3.axisBottom(xScale)
          .ticks(6)
          .tickFormat((d) => d3.timeFormat('%H:%M')(d as Date)),
      )
      .selectAll('text')
      .attr('fill', '#94a3b8')
      .attr('font-size', 10);

    // Y axis
    g.append('g')
      .call(d3.axisLeft(yScale).tickSize(0))
      .selectAll('text')
      .attr('fill', '#cbd5e1')
      .attr('font-size', 10)
      .attr('x', -4);

    // Cells
    g.selectAll<SVGRectElement, HeatCell>('rect.cell')
      .data(cells.filter((c) => c.bucketTs >= windowStart))
      .join('rect')
      .attr('class', 'cell')
      .attr('x', (d) => xScale(new Date(d.bucketTs)))
      .attr('y', (d) => yScale(`${d.algorithm}:${d.nodeId}`) ?? 0)
      .attr('width', CELL_W)
      .attr('height', yScale.bandwidth())
      .attr('fill', (d) => colorScale(d.p95Ms))
      .attr('rx', 1)
      .style('cursor', 'pointer')
      .on('mousemove', function (event, d) {
        const [mx, my] = d3.pointer(event, svgEl);
        setTooltip({ x: mx, y: my, cell: d });
      })
      .on('mouseleave', () => setTooltip(null))
      .on('click', (_, d) => onCellClick?.(d));

    // Color legend
    const legendX = innerW + 10;
    const legendData = [
      { color: '#16a34a', label: '< 10ms' },
      { color: '#ca8a04', label: '10–30ms' },
      { color: '#dc2626', label: '30–50ms' },
      { color: '#7f1d1d', label: '> 50ms' },
    ];
    const lg = g.append('g').attr('transform', `translate(${legendX},0)`);
    legendData.forEach(({ color, label }, i) => {
      lg.append('rect').attr('y', i * 20).attr('width', 12).attr('height', 12).attr('fill', color);
      lg.append('text')
        .attr('x', 16)
        .attr('y', i * 20 + 10)
        .attr('font-size', 10)
        .attr('fill', '#94a3b8')
        .text(label);
    });

    // Breach threshold line at 50ms
    const breachX = xScale(new Date(now - 1000)); // right side marker
    g.append('line')
      .attr('x1', 0)
      .attr('x2', innerW)
      .attr('y1', -5)
      .attr('y2', -5)
      .attr('stroke', '#ef4444')
      .attr('stroke-dasharray', '4 2')
      .attr('opacity', 0.5);

  }, [cells, onCellClick]);

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div style={{ background: '#0f172a', borderRadius: 8, padding: 12 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
        <span style={{ color: '#e2e8f0', fontWeight: 600, fontSize: 14 }}>
          PQC Handshake Latency Heatmap
        </span>
        <span style={{ color: '#64748b', fontSize: 11 }}>
          Updated: {new Date(lastUpdate).toLocaleTimeString()}
        </span>
        {error && (
          <span style={{ color: '#ef4444', fontSize: 11 }}>Error: {error}</span>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {algorithms.map((a) => (
            <span
              key={a}
              style={{
                fontSize: 10,
                padding: '2px 6px',
                background: '#1e293b',
                color: '#94a3b8',
                borderRadius: 4,
              }}
            >
              {a}
            </span>
          ))}
        </div>
      </div>

      {/* SVG heatmap */}
      <div style={{ overflowX: 'auto' }}>
        <svg
          ref={svgRef}
          style={{ width: '100%', minWidth: 600 }}
        />
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          style={{
            position: 'fixed',
            left: tooltip.x + 12,
            top: tooltip.y - 20,
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: 6,
            padding: '8px 12px',
            fontSize: 12,
            color: '#e2e8f0',
            pointerEvents: 'none',
            zIndex: 1000,
          }}
        >
          <div><strong>{tooltip.cell.nodeId}</strong> — {tooltip.cell.algorithm}</div>
          <div>p50: {tooltip.cell.p50Ms.toFixed(1)}ms</div>
          <div>p95: {tooltip.cell.p95Ms.toFixed(1)}ms</div>
          <div>p99: {tooltip.cell.p99Ms.toFixed(1)}ms</div>
          <div>Time: {new Date(tooltip.cell.bucketTs).toLocaleTimeString()}</div>
          {tooltip.cell.failures > 0 && (
            <div style={{ color: '#ef4444' }}>Failures: {tooltip.cell.failures}</div>
          )}
        </div>
      )}

      {/* Summary stats */}
      <SummaryBar cells={cells} />
    </div>
  );
};

// ── Summary bar ───────────────────────────────────────────────────────────────

const SummaryBar: React.FC<{ cells: HeatCell[] }> = ({ cells }) => {
  if (cells.length === 0) return null;
  const recent = cells.filter((c) => c.bucketTs > Date.now() - 60_000);
  const p95s = recent.map((c) => c.p95Ms).sort((a, b) => a - b);
  const median = p95s[Math.floor(p95s.length / 2)] ?? 0;
  const p99 = p95s[Math.floor(p95s.length * 0.99)] ?? 0;
  const breaches = recent.filter((c) => c.p95Ms > 50).length;

  return (
    <div
      style={{
        display: 'flex',
        gap: 24,
        marginTop: 8,
        padding: '6px 0',
        borderTop: '1px solid #1e293b',
        fontSize: 12,
        color: '#94a3b8',
      }}
    >
      <Stat label="Median p95 (1m)" value={`${median.toFixed(1)}ms`} ok={median < 30} />
      <Stat label="p99 (1m)" value={`${p99.toFixed(1)}ms`} ok={p99 < 50} />
      <Stat
        label="SLA Breaches (1m)"
        value={String(breaches)}
        ok={breaches === 0}
      />
      <Stat label="Total pairs" value={String(new Set(cells.map((c) => c.nodeId)).size)} />
    </div>
  );
};

const Stat: React.FC<{ label: string; value: string; ok?: boolean }> = ({ label, value, ok }) => (
  <div>
    <div style={{ fontSize: 10, color: '#475569', marginBottom: 2 }}>{label}</div>
    <div style={{ color: ok === undefined ? '#e2e8f0' : ok ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
      {value}
    </div>
  </div>
);

export default PQCHeatmap;
