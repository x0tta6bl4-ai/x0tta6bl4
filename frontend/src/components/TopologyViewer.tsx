import React, { useEffect, useRef, useCallback, useState } from 'react';
import * as d3 from 'd3';

// ── Types ────────────────────────────────────────────────────────────────────

interface MeshNode {
  id: string;
  name: string;
  status: 'active' | 'degraded' | 'down' | 'pending';
  region?: string;
  lastRssi?: number;
  lastSnr?: number;
  lastLatencyMs?: number;
  uptimePct?: number;
}

interface Edge {
  source: string;
  target: string;
  latencyMs: number;
}

interface Topology {
  nodes: MeshNode[];
  edges: Edge[];
  cachedAt: number;
}

interface SimNode extends d3.SimulationNodeDatum, MeshNode {}
interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  latencyMs: number;
}

// ── Constants ────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<MeshNode['status'], string> = {
  active: '#22c55e',
  degraded: '#f59e0b',
  down: '#ef4444',
  pending: '#6b7280',
};

const WS_RECONNECT_DELAY_MS = 3_000;
const API_POLL_INTERVAL_MS = 10_000;

// ── Component ────────────────────────────────────────────────────────────────

interface Props {
  apiBase?: string;
  wsUrl?: string;
  onNodeSelect?: (node: MeshNode | null) => void;
}

export const TopologyViewer: React.FC<Props> = ({
  apiBase = '/api',
  wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/topology`,
  onNodeSelect,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const simRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [topology, setTopology] = useState<Topology | null>(null);
  const [selectedNode, setSelectedNode] = useState<MeshNode | null>(null);
  const [wsStatus, setWsStatus] = useState<'connecting' | 'open' | 'closed'>('connecting');

  // ── Fetch topology (fallback poll) ───────────────────────────────────────

  const fetchTopology = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/mesh/topology`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('jwt') ?? ''}` },
      });
      if (res.ok) setTopology(await res.json());
    } catch {
      // non-fatal: WS is primary source
    }
  }, [apiBase]);

  useEffect(() => {
    fetchTopology();
    const interval = setInterval(fetchTopology, API_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchTopology]);

  // ── WebSocket real-time updates ──────────────────────────────────────────

  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>;

    function connect() {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      setWsStatus('connecting');

      ws.onopen = () => setWsStatus('open');

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'topology') setTopology(msg.data);
        } catch {
          // ignore malformed frames
        }
      };

      ws.onclose = () => {
        setWsStatus('closed');
        timeout = setTimeout(connect, WS_RECONNECT_DELAY_MS);
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      clearTimeout(timeout);
      wsRef.current?.close();
    };
  }, [wsUrl]);

  // ── D3 force simulation ──────────────────────────────────────────────────

  useEffect(() => {
    if (!topology || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const { width, height } = svgRef.current.getBoundingClientRect();

    // Build sim data
    const nodes: SimNode[] = topology.nodes.map((n) => ({ ...n }));
    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    const links: SimLink[] = topology.edges
      .map((e) => ({
        source: nodeById.get(e.source) ?? e.source,
        target: nodeById.get(e.target) ?? e.target,
        latencyMs: e.latencyMs,
      }))
      .filter((l) => l.source && l.target);

    // Clear previous render
    svg.selectAll('*').remove();

    // Zoom container
    const g = svg.append('g');
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 4])
        .on('zoom', ({ transform }) => g.attr('transform', transform)),
    );

    // Arrow marker
    svg
      .append('defs')
      .append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 18)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#94a3b8');

    // Links
    const link = g
      .selectAll<SVGLineElement, SimLink>('line')
      .data(links)
      .join('line')
      .attr('stroke', (d) => latencyColor(d.latencyMs))
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrow)')
      .attr('opacity', 0.7);

    // Edge latency labels
    const edgeLabel = g
      .selectAll<SVGTextElement, SimLink>('text.edge-label')
      .data(links)
      .join('text')
      .attr('class', 'edge-label')
      .attr('font-size', 9)
      .attr('fill', '#94a3b8')
      .attr('text-anchor', 'middle')
      .text((d) => `${d.latencyMs}ms`);

    // Node groups
    const node = g
      .selectAll<SVGGElement, SimNode>('g.node')
      .data(nodes)
      .join('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .call(
        d3
          .drag<SVGGElement, SimNode>()
          .on('start', (event, d) => {
            if (!event.active) simRef.current?.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simRef.current?.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }),
      )
      .on('click', (_, d) => {
        setSelectedNode(d);
        onNodeSelect?.(d);
      });

    node
      .append('circle')
      .attr('r', 12)
      .attr('fill', (d) => STATUS_COLOR[d.status])
      .attr('stroke', '#1e293b')
      .attr('stroke-width', 2);

    node
      .append('text')
      .attr('dy', 26)
      .attr('text-anchor', 'middle')
      .attr('font-size', 10)
      .attr('fill', '#e2e8f0')
      .text((d) => d.name);

    // Simulation
    const sim = d3
      .forceSimulation<SimNode>(nodes)
      .force(
        'link',
        d3
          .forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(100),
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(20));

    simRef.current = sim;

    sim.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x ?? 0)
        .attr('y1', (d) => (d.source as SimNode).y ?? 0)
        .attr('x2', (d) => (d.target as SimNode).x ?? 0)
        .attr('y2', (d) => (d.target as SimNode).y ?? 0);

      edgeLabel
        .attr(
          'x',
          (d) => (((d.source as SimNode).x ?? 0) + ((d.target as SimNode).x ?? 0)) / 2,
        )
        .attr(
          'y',
          (d) => (((d.source as SimNode).y ?? 0) + ((d.target as SimNode).y ?? 0)) / 2,
        );

      node.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      sim.stop();
    };
  }, [topology, onNodeSelect]);

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#0f172a' }}>
      {/* Status bar */}
      <div
        style={{
          padding: '6px 12px',
          background: '#1e293b',
          fontSize: 12,
          color: '#94a3b8',
          display: 'flex',
          gap: 16,
          alignItems: 'center',
        }}
      >
        <span>
          WS:{' '}
          <span style={{ color: wsStatus === 'open' ? '#22c55e' : '#ef4444' }}>{wsStatus}</span>
        </span>
        {topology && (
          <>
            <span>Nodes: {topology.nodes.length}</span>
            <span>Edges: {topology.edges.length}</span>
            <span>
              Active: {topology.nodes.filter((n) => n.status === 'active').length}
            </span>
            <span style={{ marginLeft: 'auto' }}>
              Cached: {new Date(topology.cachedAt).toLocaleTimeString()}
            </span>
          </>
        )}
      </div>

      {/* Graph */}
      <svg ref={svgRef} style={{ flex: 1, width: '100%' }} />

      {/* Legend */}
      <div
        style={{
          position: 'absolute',
          top: 48,
          right: 12,
          background: '#1e293b',
          borderRadius: 6,
          padding: '8px 12px',
          fontSize: 11,
          color: '#94a3b8',
        }}
      >
        {Object.entries(STATUS_COLOR).map(([status, color]) => (
          <div key={status} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
            {status}
          </div>
        ))}
        <div style={{ marginTop: 6, borderTop: '1px solid #334155', paddingTop: 6 }}>
          <div style={{ color: '#22c55e' }}>&#9135; &lt; 10ms</div>
          <div style={{ color: '#f59e0b' }}>&#9135; 10–50ms</div>
          <div style={{ color: '#ef4444' }}>&#9135; &gt; 50ms</div>
        </div>
      </div>
    </div>
  );
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function latencyColor(ms: number): string {
  if (ms < 10) return '#22c55e';
  if (ms < 50) return '#f59e0b';
  return '#ef4444';
}

export default TopologyViewer;
